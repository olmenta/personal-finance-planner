"""Review of uncategorized transactions (spec: transaction-review) —
suggestion service mocked, no live calls."""

from unittest.mock import patch

from sqlalchemy import select

from app.models import Payee, Transaction
from app.services.category_suggestions import EMPTY, Suggestion

SUGGEST = "app.routers.transactions.category_suggestions.suggest"


def make_uncategorized(client, db, category_id, note, date="2026-06-05", amount=500, account_id=None):
    """Confirmed uncategorized row: created normally, then category stripped."""
    body = {"amount_cents": amount, "category_id": category_id, "note": note, "date": date}
    if account_id:
        body["account_id"] = account_id
    txn_id = client.post("/transactions", json=body).json()["id"]
    db.query(Transaction).filter_by(id=txn_id).update({"category_id": None})
    db.flush()
    return txn_id


def no_ai(categories, rows, history=None):
    return {i: EMPTY for i in range(len(rows))}


def review(client, fake=no_ai) -> list[dict]:
    with patch(SUGGEST, fake):
        response = client.post("/transactions/review")
    assert response.status_code == 200
    return response.json()["transactions"]


def apply(client, **maps) -> dict:
    return client.post("/transactions/review/apply", json=maps).json()


def make_banks(client) -> tuple[str, str]:
    a = client.post("/accounts", json={"name": "BBVA", "type": "bank"}).json()["id"]
    b = client.post("/accounts", json={"name": "Banco B", "type": "bank"}).json()["id"]
    return a, b


def test_lists_every_uncategorized_row_newest_first(client, db, category_ids):
    super_id = category_ids["Supermercado"]
    june = make_uncategorized(client, db, super_id, "JUNE", date="2026-06-05")
    august = make_uncategorized(client, db, super_id, "AUGUST", date="2026-08-20")
    july = make_uncategorized(client, db, super_id, "JULY", date="2026-07-11")
    # Not listed: categorized rows, transfer twins, opening balances.
    client.post("/transactions", json={"amount_cents": 900, "category_id": super_id, "date": "2026-07-01"})
    a, b = make_banks(client)
    client.post("/transfers", json={"from_account_id": a, "to_account_id": b, "amount_cents": 5000, "date": "2026-07-02"})
    client.post("/accounts", json={"name": "Visa", "type": "credit", "opening_balance_cents": -34000})

    rows = review(client)
    assert [r["id"] for r in rows] == [august, july, june]
    assert all(r["suggested_category_id"] is None and r["confidence"] is None for r in rows)


def test_ai_suggestion_is_a_default_never_written(client, db, category_ids):
    target = make_uncategorized(client, db, category_ids["Supermercado"], "MERCADONA 1")

    def fake(categories, rows, history=None):
        return {i: Suggestion(category_ids["Supermercado"], "Mercadona", "high") for i in range(len(rows))}

    [row] = review(client, fake)
    assert row["id"] == target
    assert row["category_id"] is None
    assert row["suggested_category_id"] == category_ids["Supermercado"]
    assert row["suggested_payee"] == "Mercadona"
    assert row["confidence"] == "high"
    stored = db.get(Transaction, target)
    assert stored.category_id is None and stored.payee_id is None


def test_ai_failure_still_lists_rows(client, db, category_ids):
    target = make_uncategorized(client, db, category_ids["Supermercado"], "WHATEVER")

    def boom(categories, rows, history=None):
        return {}

    rows = review(client, boom)
    assert [r["id"] for r in rows] == [target]
    assert rows[0]["suggested_category_id"] is None


def test_apply_category_payee_and_note(client, db, category_ids):
    target = make_uncategorized(client, db, category_ids["Supermercado"], "MERCADONA 123")
    body = apply(
        client,
        overrides={target: category_ids["Gasolina"]},
        payee_overrides={target: "Repsol"},
        note_overrides={target: "  Gasolina del coche  "},
    )
    assert body == {"applied": 1}
    row = db.get(Transaction, target)
    assert row.category_id == category_ids["Gasolina"]
    assert db.get(Payee, row.payee_id).name == "Repsol"
    assert row.description == "Gasolina del coche"


def test_apply_skips_foreign_categorized_and_invalid(client, db, category_ids):
    target = make_uncategorized(client, db, category_ids["Supermercado"], "ROW")
    categorized = client.post(
        "/transactions",
        json={"amount_cents": 900, "category_id": category_ids["Gasolina"], "date": "2026-06-07"},
    ).json()["id"]
    body = apply(
        client,
        overrides={
            target: "not-a-category",
            categorized: category_ids["Supermercado"],
            "not-yours": category_ids["Supermercado"],
        },
    )
    assert body == {"applied": 0}
    assert db.get(Transaction, target).category_id is None
    assert db.get(Transaction, categorized).category_id == category_ids["Gasolina"]


def test_transfer_marked_on_confirmed_row(client, db, category_ids):
    a, b = make_banks(client)
    target = make_uncategorized(client, db, category_ids["Supermercado"], "TRASPASO", amount=20000, account_id=a)
    income_before = client.get("/budget/2026-06").json()["income_cents"]

    body = apply(client, transfer_overrides={target: b})
    assert body == {"applied": 1}
    near = db.get(Transaction, target)
    twin = db.scalar(
        select(Transaction).where(
            Transaction.transfer_pair_id == near.transfer_pair_id, Transaction.id != near.id
        )
    )
    assert twin.account_id == b and twin.amount_cents == 20000 and twin.status == "confirmed"
    assert near.category_id is None and twin.category_id is None
    assert client.get("/budget/2026-06").json()["income_cents"] == income_before
    # A transfer is resolved: it leaves the review.
    assert target not in [r["id"] for r in review(client)]


def test_twin_match_suggested_and_adopted(client, db, category_ids):
    a, b = make_banks(client)
    client.post(
        "/transfers",
        json={"from_account_id": a, "to_account_id": b, "amount_cents": 20000, "date": "2026-06-10"},
    )
    # Banco B's side of that transfer, recorded again by hand as income.
    duplicate = client.post(
        "/transactions",
        json={"amount_cents": 20000, "kind": "income", "date": "2026-06-12", "account_id": b},
    ).json()["id"]

    [row] = [r for r in review(client) if r["id"] == duplicate]
    assert row["match"] is not None and row["match"]["other_account_id"] == a
    # A suggestion links nothing by itself.
    assert db.get(Transaction, duplicate).transfer_pair_id is None

    body = apply(client, accept_matches=[duplicate])
    assert body == {"applied": 1}
    assert db.get(Transaction, duplicate) is None
    in_b = db.scalars(
        select(Transaction).where(Transaction.account_id == b, Transaction.amount_cents == 20000)
    ).all()
    assert len(in_b) == 1 and in_b[0].transfer_pair_id is not None


def test_untouched_rows_stay_as_they_are(client, db, category_ids):
    kept = make_uncategorized(client, db, category_ids["Supermercado"], "KEEP ME")
    changed = make_uncategorized(client, db, category_ids["Supermercado"], "CHANGE ME")
    apply(client, overrides={changed: category_ids["Gasolina"]})
    row = db.get(Transaction, kept)
    assert row.category_id is None and row.description == "KEEP ME"
