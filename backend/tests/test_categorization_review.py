"""On-demand suggest/apply endpoints — suggestion service mocked, no live calls."""

from unittest.mock import patch

from app.models import Payee, Transaction
from app.services.category_suggestions import EMPTY, Suggestion


def make_uncategorized(client, db, category_id, note, date="2026-06-05", amount=500):
    """Confirmed uncategorized row: created normally, then category stripped."""
    body = client.post(
        "/transactions",
        json={"amount_cents": amount, "category_id": category_id, "note": note, "date": date},
    ).json()
    db.query(Transaction).filter_by(id=body["id"]).update({"category_id": None})
    db.flush()
    return body["id"]


def suggest_all(category_id, payee="Mercadona", confidence="high"):
    def fake(categories, rows, history=None):
        return {i: Suggestion(category_id, payee, confidence) for i in range(len(rows))}

    return fake


def test_default_targets_confirmed_uncategorized_only(client, db, category_ids):
    target = make_uncategorized(client, db, category_ids["Supermercado"], "MERCADONA 1")
    # Categorized row must not be targeted.
    client.post(
        "/transactions",
        json={"amount_cents": 900, "category_id": category_ids["Gasolina"], "note": "REPSOL"},
    )

    captured = {}

    def fake(categories, rows, history=None):
        captured["rows"] = rows
        return {i: Suggestion(category_ids["Supermercado"], "Mercadona", "high") for i in range(len(rows))}

    with patch("app.routers.transactions.category_suggestions.suggest", fake):
        body = client.post("/transactions/suggest-categories", json={}).json()

    assert len(captured["rows"]) == 1
    assert captured["rows"][0].description == "MERCADONA 1"
    assert body["proposals"] == [
        {
            "transaction_id": target,
            "category_id": category_ids["Supermercado"],
            "payee": "Mercadona",
            "confidence": "high",
        }
    ]
    # Proposals never write.
    row = db.query(Transaction).filter_by(id=target).one()
    assert row.category_id is None and row.payee_id is None


def test_explicit_ids_owner_scoped(client, db, category_ids):
    txn_id = make_uncategorized(client, db, category_ids["Supermercado"], "ROW A")
    with patch(
        "app.routers.transactions.category_suggestions.suggest",
        suggest_all(category_ids["Supermercado"]),
    ):
        body = client.post(
            "/transactions/suggest-categories",
            json={"transaction_ids": [txn_id, "not-yours"]},
        ).json()
    assert [p["transaction_id"] for p in body["proposals"]] == [txn_id]


def test_ai_failure_degrades_to_empty(client, db, category_ids):
    make_uncategorized(client, db, category_ids["Supermercado"], "WHATEVER")

    def all_empty(categories, rows, history=None):
        return {i: EMPTY for i in range(len(rows))}

    with patch("app.routers.transactions.category_suggestions.suggest", all_empty):
        response = client.post("/transactions/suggest-categories", json={})
    assert response.status_code == 200
    assert response.json() == {"proposals": []}


def test_apply_writes_accepted_subset_and_skips_invalid(client, db, user, category_ids):
    keep = make_uncategorized(client, db, category_ids["Supermercado"], "KEEP")
    vanished = make_uncategorized(client, db, category_ids["Supermercado"], "GONE")
    db.query(Transaction).filter_by(id=vanished).delete()
    db.flush()

    response = client.post(
        "/transactions/apply-categories",
        json={
            "assignments": {
                keep: {"category_id": category_ids["Gasolina"], "payee": "Repsol"},
                vanished: {"category_id": category_ids["Gasolina"]},
                "unknown": {"category_id": category_ids["Gasolina"]},
            }
        },
    )
    assert response.status_code == 200
    assert response.json() == {"applied": 1}

    row = db.query(Transaction).filter_by(id=keep).one()
    assert row.category_id == category_ids["Gasolina"]
    assert db.query(Payee).filter_by(id=row.payee_id).one().name == "Repsol"


def test_apply_rejects_foreign_category_and_clears_payee(client, db, user, category_ids):
    txn = make_uncategorized(client, db, category_ids["Supermercado"], "ROW")
    # Invalid category: whole assignment skipped.
    body = client.post(
        "/transactions/apply-categories",
        json={"assignments": {txn: {"category_id": "nope", "payee": "X"}}},
    ).json()
    assert body == {"applied": 0}
    assert db.query(Transaction).filter_by(id=txn).one().payee_id is None

    # Set then clear the payee with "".
    client.post(
        "/transactions/apply-categories",
        json={"assignments": {txn: {"payee": "Mercadona"}}},
    )
    assert db.query(Transaction).filter_by(id=txn).one().payee_id is not None
    body = client.post(
        "/transactions/apply-categories",
        json={"assignments": {txn: {"payee": ""}}},
    ).json()
    assert body == {"applied": 1}
    assert db.query(Transaction).filter_by(id=txn).one().payee_id is None


def test_apply_explicit_null_clears_category_absent_leaves_it(client, db, category_ids):
    """A categorized inflow (refund) set back to "Ready to assign" becomes
    income; omitting category_id leaves another row untouched."""
    refund = client.post(
        "/transactions",
        json={"amount_cents": 1250, "kind": "income", "category_id": category_ids["Supermercado"], "date": "2026-06-10"},
    ).json()["id"]
    untouched = client.post(
        "/transactions",
        json={"amount_cents": 900, "kind": "income", "category_id": category_ids["Supermercado"], "date": "2026-06-11"},
    ).json()["id"]
    income_before = client.get("/budget/2026-06").json()["income_cents"]

    response = client.post(
        "/transactions/apply-categories",
        json={"assignments": {refund: {"category_id": None}, untouched: {"payee": "Mercadona"}}},
    )
    assert response.json() == {"applied": 2}
    assert db.get(Transaction, refund).category_id is None
    assert db.get(Transaction, untouched).category_id == category_ids["Supermercado"]
    assert client.get("/budget/2026-06").json()["income_cents"] == income_before + 1250
