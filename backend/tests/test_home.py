"""Home snapshot: summary mapping, statuses, grouping and version
(openspec change redesign-home-navigation)."""

import random
from datetime import date

import pytest

from app import clock

HISTORY = ["2026-07", "2026-08", "2026-09"]


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    set_today(monkeypatch, date(2026, 10, 14))


def set_today(monkeypatch, today: date) -> None:
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)


def home(client) -> dict:
    response = client.get("/home")
    assert response.status_code == 200, response.text
    return response.json()


def bank(client, cents: int = 0) -> str:
    return client.post("/accounts", json={"name": "Banco", "type": "bank",
                                          "opening_balance_cents": cents}).json()["id"]


def identity(h: dict) -> bool:
    s = h["summary"]
    return s["accounts_cents"] == (s["covered_cents"] + s["left_to_spend_cents"]
                                   + s["saved_cents"] + s["unassigned_cents"])


def reason(h: dict, code: str) -> dict | None:
    return next((r for r in h["reasons"] if r["code"] == code), None)


def test_identity_over_generated_data(client, category_ids):
    rng = random.Random(11)
    bank(client, 300000)
    ids = list(category_ids.values())
    client.get("/budget/2026-10")
    for cid in rng.sample(ids, 3):
        client.post(f"/categories/{cid}/schedules", json={
            "name": "P", "amount_cents": rng.randint(1000, 60000), "pattern": "monthly",
            "day": rng.randint(1, 28)})
    for cid in rng.sample(ids, 4):
        client.put(f"/budget/2026-10/assignments/{cid}", json={"amount_cents": rng.randint(0, 50000)})
    for _ in range(10):
        client.post("/transactions", json={"amount_cents": rng.randint(500, 40000),
                                           "category_id": rng.choice(ids),
                                           "date": f"2026-10-{rng.randint(1, 14):02d}"})
    assert identity(home(client))


def fresh_user(db):
    """A user as Auth0 provisioning leaves them: the empty cash account, no
    categories, no transactions (auth0-users)."""
    from app.services import users
    return users.resolve(db, "auth0|fresh", "fresh@example.com")


def test_not_set_up_before_the_onboarding(db, client):
    from app.services.home import build_home
    h = build_home(db, fresh_user(db))
    assert h.status == "not_set_up"
    assert h.reasons == [] and h.priority is None and h.groups == []
    assert h.summary.accounts_cents == 0


def test_the_starter_template_sets_up(db, client):
    from app.services.category_setup import DEFAULT_CATEGORY_TREE, create_tree
    from app.services.home import build_home
    user = fresh_user(db)
    create_tree(db, user.id, DEFAULT_CATEGORY_TREE)
    assert build_home(db, user).status != "not_set_up"


def test_recorded_money_sets_up(db, client):
    from sqlalchemy import select
    from app.models import Account
    from app.services.accounts import write_opening_balance
    from app.services.home import build_home
    user = fresh_user(db)
    cash = db.scalar(select(Account).where(Account.user_id == user.id))
    write_opening_balance(db, cash, 5000, date(2026, 10, 14))
    db.flush()
    assert build_home(db, user).status != "not_set_up"


def test_no_accounts(client):
    for account in client.get("/accounts").json():  # the seed's default account
        client.patch(f"/accounts/{account['id']}", json={"archived": True})
    h = home(client)
    assert h["status"] == "no_accounts"


def test_organized_month(client, category_ids):
    bank(client, 100000)
    client.get("/budget/2026-10")
    client.put(f"/budget/2026-10/assignments/{category_ids['Supermercado']}", json={"amount_cents": 40000})
    client.post("/transactions", json={"amount_cents": 1000, "category_id": category_ids["Supermercado"],
                                       "date": "2026-10-10"})
    h = home(client)
    assert h["status"] == "organized" and h["reasons"] == []
    assert h["summary"]["left_to_spend_cents"] == 39000
    assert identity(h)


def test_unassigned_money_and_overspent_categories_at_once(client, category_ids):
    """The screenshot situation: lots unassigned, yet day-to-day overspent."""
    bank(client, 500000)
    client.get("/budget/2026-10")
    client.post("/transactions", json={"amount_cents": 30000, "category_id": category_ids["Ocio"],
                                       "date": "2026-10-05"})
    h = home(client)
    assert h["status"] == "needs_organizing"
    over = reason(h, "overspent_categories")
    assert over["amount_cents"] == 30000
    assert [i["name"] for i in over["items"]] == ["Ocio"]
    assert h["summary"]["left_to_spend_cents"] == -30000
    assert h["summary"]["unassigned_cents"] > 0
    assert identity(h)


def test_over_assigned_and_uncovered_payments(client, category_ids):
    bank(client, 0)
    client.get("/budget/2026-10")
    client.put(f"/budget/2026-10/assignments/{category_ids['Supermercado']}", json={"amount_cents": 20000})
    alquiler = category_ids["Alquiler"]
    client.post(f"/categories/{alquiler}/schedules", json={
        "name": "Alquiler", "amount_cents": 95200, "pattern": "monthly", "day": 28})
    client.post("/budget/2026-10/moves", json={"from_category_id": alquiler,
                                                "to_category_id": category_ids["Ocio"],
                                                "amount_cents": 50000})
    h = home(client)
    assert reason(h, "over_assigned")["amount_cents"] == -h["summary"]["unassigned_cents"]
    assert reason(h, "uncovered_payments")["amount_cents"] == 50000
    assert identity(h)


def test_unbudgeted_card_spending(client, category_ids):
    bank(client, 100000)
    visa = client.post("/accounts", json={"name": "Visa", "type": "credit"}).json()["id"]
    client.post("/transactions", json={"amount_cents": 5000, "category_id": category_ids["Ocio"],
                                       "account_id": visa, "date": "2026-10-05"})
    assert reason(home(client), "unbudgeted_card_spending")["amount_cents"] == 5000


def test_data_status(client, category_ids, monkeypatch):
    bank(client)  # no opening balance: the expense is the newest transaction
    client.post("/transactions", json={"amount_cents": 2000, "kind": "expense",
                                       "category_id": category_ids["Ocio"], "date": "2026-10-10"})
    h = home(client)
    assert h["data"]["last_transaction_date"] == "2026-10-10"
    assert h["data"]["limited"] is False
    set_today(monkeypatch, date(2026, 10, 30))  # 20 days without transactions
    assert home(client)["data"]["limited"] is True


def test_future_status(client, category_ids):
    bank(client, 100000)
    assert home(client)["future"]["status"] == "unknown"
    client.post("/income-schedules", json={"name": "Nómina", "amount_cents": 100000,
                                           "pattern": "monthly", "day": 1})
    assert home(client)["future"]["status"] == "on_track"
    seguro = category_ids["Ocio"]
    client.post(f"/categories/{seguro}/schedules", json={
        "name": "Seguro", "amount_cents": 900000, "pattern": "annual", "month": 3})
    future = home(client)["future"]
    assert future["status"] == "needs_attention"
    assert future["set_aside_gap_cents"] > 0 or future["short_cents"] > 0


def test_priority_not_repeated_and_groups_ordered(client, category_ids):
    bank(client, 200000)
    for name, assigned, spent in [("Restaurantes", 20000, [24000, 19000, 25000]),
                                  ("Gasolina", 12000, [5500, 6200, 5800])]:
        for month, amount in zip(HISTORY, spent):
            client.get(f"/budget/{month}")
            client.put(f"/budget/{month}/assignments/{category_ids[name]}", json={"amount_cents": assigned})
            client.post("/transactions", json={"amount_cents": amount, "category_id": category_ids[name],
                                               "date": f"{month}-10"})
    client.post("/income-schedules", json={"name": "Nómina", "amount_cents": 1000,
                                           "pattern": "monthly", "day": 5, "payer": "Acme"})
    h = home(client)
    assert h["priority"]["kind"] == "late_income"
    keys = [g["key"] for g in h["groups"]]
    assert keys.index("adjustments") < keys.index("unassigned") if "unassigned" in keys else True
    all_fps = [p["fingerprint"] for g in h["groups"] for p in g["proposals"]]
    assert h["priority"]["fingerprint"] not in all_fps
    adjustments = next(g for g in h["groups"] if g["key"] == "adjustments")
    assert {p["kind"] for p in adjustments["proposals"]} == {"overspending", "underspending"}


def test_snapshot_version(client, category_ids):
    bank(client, 100000)
    first, second = home(client), home(client)
    assert first["snapshot_version"] == second["snapshot_version"]
    client.post("/transactions", json={"amount_cents": 1500, "category_id": category_ids["Ocio"],
                                       "date": "2026-10-12"})
    assert home(client)["snapshot_version"] != first["snapshot_version"]


def test_the_coach_is_told_not_to_analyze_before_setup(db, client):
    from app.services.coach_chat import _context
    from app.services.home import build_home
    context = _context(build_home(db, fresh_user(db)), "es")
    assert "hasn't set up their budget" in context
    assert "money in accounts" not in context
