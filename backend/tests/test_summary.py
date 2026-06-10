from datetime import date

from app.models import Transaction
from app.services.summary import week_starts


def test_week_starts_cover_month_monday_based():
    # June 2026: the 1st is a Monday → exactly 5 Monday buckets.
    starts = week_starts("2026-06")
    assert starts == [
        date(2026, 6, 1),
        date(2026, 6, 8),
        date(2026, 6, 15),
        date(2026, 6, 22),
        date(2026, 6, 29),
    ]
    # May 2026: the 1st is a Friday → clamped first bucket, then Mondays.
    may = week_starts("2026-05")
    assert may[0] == date(2026, 5, 1)
    assert all(s.weekday() == 0 for s in may[1:])


def test_month_totals_exclude_staged(client, db, user, category_ids):
    ocio = category_ids["Ocio"]
    client.post(
        "/transactions",
        json={"amount_cents": 193800, "category_id": ocio, "date": "2026-06-09"},
    )
    client.post(
        "/transactions",
        json={"amount_cents": 235000, "category_id": ocio, "kind": "income", "date": "2026-06-01"},
    )
    account_id = db.query(Transaction).first().account_id
    db.add(
        Transaction(
            user_id=user.id,
            account_id=account_id,
            category_id=ocio,
            date=date(2026, 6, 4),
            amount_cents=-5000,
            status="staged",
            dedupe_hash="staged-summary",
        )
    )
    db.flush()

    view = client.get("/summary/2026-06").json()
    assert view["income_cents"] == 235000
    assert view["expense_cents"] == 193800


def test_balance_spans_months(client, category_ids):
    ocio = category_ids["Ocio"]
    client.post(
        "/transactions",
        json={"amount_cents": 100000, "category_id": ocio, "kind": "income", "date": "2026-05-15"},
    )
    client.post(
        "/transactions",
        json={"amount_cents": 12543, "category_id": ocio, "date": "2026-06-03"},
    )
    june = client.get("/summary/2026-06").json()
    may = client.get("/summary/2026-05").json()
    assert june["balance_cents"] == 100000 - 12543
    # Balance is all-time, identical regardless of the requested month.
    assert may["balance_cents"] == june["balance_cents"]


def test_buckets_cover_and_sum_to_totals(client, category_ids):
    ocio = category_ids["Ocio"]
    for day, cents in (("2026-06-01", 1000), ("2026-06-08", 2000), ("2026-06-30", 3000)):
        client.post(
            "/transactions", json={"amount_cents": cents, "category_id": ocio, "date": day}
        )
    client.post(
        "/transactions",
        json={"amount_cents": 50000, "category_id": ocio, "kind": "income", "date": "2026-06-10"},
    )
    view = client.get("/summary/2026-06").json()
    weeks = view["weeks"]
    assert [w["start"] for w in weeks] == [
        "2026-06-01",
        "2026-06-08",
        "2026-06-15",
        "2026-06-22",
        "2026-06-29",
    ]
    assert sum(w["spent_cents"] for w in weeks) == view["expense_cents"] == 6000
    assert sum(w["income_cents"] for w in weeks) == view["income_cents"] == 50000
    assert weeks[0]["spent_cents"] == 1000
    assert weeks[1]["spent_cents"] == 2000
    assert weeks[1]["income_cents"] == 50000
    assert weeks[4]["spent_cents"] == 3000


def test_empty_month_returns_zeros(client):
    view = client.get("/summary/2026-04").json()
    assert view["balance_cents"] == 0
    assert view["income_cents"] == 0
    assert view["expense_cents"] == 0
    assert view["weeks"]
    assert all(w["spent_cents"] == 0 and w["income_cents"] == 0 for w in view["weeks"])
