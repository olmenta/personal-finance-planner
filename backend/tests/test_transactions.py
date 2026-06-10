from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Transaction


def test_minimal_entry_defaults(client, category_ids):
    response = client.post(
        "/transactions",
        json={"amount_cents": 1249, "category_id": category_ids["Restaurantes"]},
    )
    assert response.status_code == 201
    body = response.json()
    today_madrid = datetime.now(ZoneInfo("Europe/Madrid")).date().isoformat()
    assert body["date"] == today_madrid
    assert body["amount_cents"] == -1249  # expense stored signed
    assert body["source"] == "manual"
    assert body["status"] == "confirmed"
    assert body["currency"] == "EUR"


def test_income_kind_stored_positive(client, category_ids):
    response = client.post(
        "/transactions",
        json={"amount_cents": 235000, "category_id": category_ids["Ahorro"], "kind": "income"},
    )
    assert response.status_code == 201
    assert response.json()["amount_cents"] == 235000


@pytest.mark.parametrize("amount", [0, -5])
def test_invalid_amount_rejected(client, category_ids, amount):
    response = client.post(
        "/transactions",
        json={"amount_cents": amount, "category_id": category_ids["Restaurantes"]},
    )
    assert response.status_code == 422


def test_unknown_category_404(client):
    response = client.post(
        "/transactions", json={"amount_cents": 100, "category_id": "nope"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "category_not_found"


def test_month_filter_newest_first(client, category_ids):
    cat = category_ids["Supermercado"]
    client.post("/transactions", json={"amount_cents": 100, "category_id": cat, "date": "2026-05-31"})
    client.post("/transactions", json={"amount_cents": 200, "category_id": cat, "date": "2026-06-01"})
    client.post("/transactions", json={"amount_cents": 300, "category_id": cat, "date": "2026-06-15"})

    body = client.get("/transactions", params={"month": "2026-06"}).json()
    assert [t["amount_cents"] for t in body] == [-300, -200]


def test_manual_same_day_duplicates_allowed(client, category_ids):
    payload = {"amount_cents": 250, "category_id": category_ids["Restaurantes"]}
    assert client.post("/transactions", json=payload).status_code == 201
    assert client.post("/transactions", json=payload).status_code == 201  # salt allows it


def test_dedupe_constraint_rejects_identical_hash(db, user, client, category_ids):
    first = db.query(Transaction).first()
    assert first is None
    client.post(
        "/transactions",
        json={"amount_cents": 100, "category_id": category_ids["Gasolina"], "date": "2026-06-02"},
    )
    existing = db.query(Transaction).first()
    clone = Transaction(
        user_id=existing.user_id,
        account_id=existing.account_id,
        category_id=existing.category_id,
        date=existing.date,
        amount_cents=existing.amount_cents,
        dedupe_hash=existing.dedupe_hash,  # same hash, same account → must fail
    )
    db.add(clone)
    with pytest.raises(IntegrityError):
        db.flush()
