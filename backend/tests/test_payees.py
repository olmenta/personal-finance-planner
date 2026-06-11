"""Payee find-or-create on transaction writes + GET /payees memory list."""

from fixtures import bbva_xlsx
from app.models import Payee, Transaction


def post_txn(client, category_id, payee=None, date=None, **extra):
    payload = {"amount_cents": 500, "category_id": category_id, **extra}
    if payee is not None:
        payload["payee"] = payee
    if date is not None:
        payload["date"] = date
    return client.post("/transactions", json=payload)


def test_first_use_creates_payee(client, db, user, category_ids):
    response = post_txn(client, category_ids["Supermercado"], payee="Mercadona")
    assert response.status_code == 201
    body = response.json()

    payee = db.query(Payee).filter_by(user_id=user.id).one()
    assert payee.name == "Mercadona"
    assert body["payee_id"] == payee.id
    assert body["payee_name"] == "Mercadona"


def test_case_insensitive_reuse(client, db, user, category_ids):
    first = post_txn(client, category_ids["Supermercado"], payee="Mercadona").json()
    second = post_txn(client, category_ids["Supermercado"], payee="MERCADONA").json()

    assert db.query(Payee).filter_by(user_id=user.id).count() == 1
    assert second["payee_id"] == first["payee_id"]
    assert second["payee_name"] == "Mercadona"  # original casing kept


def test_payee_name_trimmed(client, db, user, category_ids):
    body = post_txn(client, category_ids["Restaurantes"], payee="  La Tasca  ").json()
    assert body["payee_name"] == "La Tasca"
    assert db.query(Payee).filter_by(user_id=user.id).one().name == "La Tasca"


def test_empty_payee_leaves_null(client, db, user, category_ids):
    for raw in (None, "", "   "):
        body = post_txn(client, category_ids["Restaurantes"], payee=raw).json()
        assert body["payee_id"] is None
        assert body["payee_name"] is None
    assert db.query(Payee).filter_by(user_id=user.id).count() == 0


def test_list_ordered_by_most_recent_use_with_memory(client, category_ids):
    post_txn(client, category_ids["Supermercado"], payee="Mercadona", date="2026-06-01")
    post_txn(client, category_ids["Restaurantes"], payee="La Tasca", date="2026-06-05")
    # Mercadona used again, most recently and with a different category:
    # it moves to the front and its memory follows the latest use.
    post_txn(client, category_ids["Gasolina"], payee="Mercadona", date="2026-06-09")

    body = client.get("/payees").json()
    assert [p["name"] for p in body] == ["Mercadona", "La Tasca"]
    assert body[0]["last_category_id"] == category_ids["Gasolina"]
    assert body[1]["last_category_id"] == category_ids["Restaurantes"]


def test_uncategorized_only_payee_has_null_memory(client, db, user, category_ids):
    # Born via a normal write, then its only transaction loses the category
    # (direct update — no PATCH endpoint yet).
    body = post_txn(client, category_ids["Supermercado"], payee="Bizum amigo").json()
    db.query(Transaction).filter_by(id=body["id"]).update({"category_id": None})
    db.flush()

    payees = client.get("/payees").json()
    assert payees == [
        {"id": body["payee_id"], "name": "Bizum amigo", "last_category_id": None}
    ]


def test_imported_rows_have_null_payee(client, db, user):
    response = client.post(
        "/imports",
        files={"file": ("export.xlsx", bbva_xlsx(), "application/octet-stream")},
        data={"bank": "bbva"},
    )
    assert response.status_code == 201
    staged = response.json()["transactions"]
    assert staged and all(
        t["payee_id"] is None and t["payee_name"] is None for t in staged
    )
    assert db.query(Payee).filter_by(user_id=user.id).count() == 0


def test_list_output_shape_includes_payee_fields(client, category_ids):
    post_txn(client, category_ids["Supermercado"], payee="Mercadona")
    post_txn(client, category_ids["Supermercado"])

    rows = client.get("/transactions").json()
    with_payee = [r for r in rows if r["payee_id"]]
    without = [r for r in rows if not r["payee_id"]]
    assert len(with_payee) == 1 and with_payee[0]["payee_name"] == "Mercadona"
    assert len(without) == 1 and without[0]["payee_name"] is None
