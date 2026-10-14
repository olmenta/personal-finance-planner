"""Coach proposals: rules, order, dismiss and accept (openspec change
coach-proposals)."""

from datetime import date

import pytest

from app import clock
from app.models import CoachProposalState
from app.services import coach

HISTORY = ["2026-07", "2026-08", "2026-09"]


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    set_today(monkeypatch, date(2026, 10, 14))


def set_today(monkeypatch, today: date) -> None:
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)


def history(client, category_id: str, assigned: int, spent: list[int]) -> None:
    for month, amount in zip(HISTORY, spent):
        client.get(f"/budget/{month}")
        client.put(f"/budget/{month}/assignments/{category_id}", json={"amount_cents": assigned})
        client.post("/transactions", json={"amount_cents": amount, "category_id": category_id,
                                           "date": f"{month}-10"})


def proposals(client) -> list[dict]:
    response = client.get("/coach/proposals")
    assert response.status_code == 200, response.text
    return response.json()["proposals"]


def by_kind(items: list[dict], kind: str) -> list[dict]:
    return [p for p in items if p["kind"] == kind]


def income(client, cents: int, day: str = "2026-10-01") -> None:
    client.post("/transactions", json={"amount_cents": cents, "kind": "income", "date": day})


# ---- Rules ------------------------------------------------------------------------------


def test_restaurants_keeps_going_over(client, category_ids):
    history(client, category_ids["Restaurantes"], 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    assert (p["category_id"], p["current_cents"], p["suggested_cents"], p["diff_cents"]) == (
        category_ids["Restaurantes"], 20000, 23000, 3000)
    assert p["title"] == "Restaurantes keeps going over"
    assert "2 of the last 3 months" in p["body"]
    assert p["action"] == "raise"


def test_fuel_always_has_money_left(client, category_ids):
    history(client, category_ids["Gasolina"], 12000, [5500, 6200, 5800])
    [p] = by_kind(proposals(client), "underspending")
    assert (p["suggested_cents"], p["diff_cents"], p["action"]) == (6000, 6000, "lower")
    assert "free 60,00 €" in p["body"]


def test_small_differences_are_ignored(client, category_ids):
    history(client, category_ids["Restaurantes"], 20000, [21000, 19000, 20500])
    items = proposals(client)
    assert by_kind(items, "overspending") == [] and by_kind(items, "underspending") == []


def test_no_proposal_without_three_months_of_history(client, category_ids):
    restaurantes = category_ids["Restaurantes"]
    for month, amount in zip(HISTORY[1:], [25000, 26000]):
        client.get(f"/budget/{month}")
        client.put(f"/budget/{month}/assignments/{restaurantes}", json={"amount_cents": 20000})
        client.post("/transactions", json={"amount_cents": amount, "category_id": restaurantes,
                                           "date": f"{month}-10"})
    assert by_kind(proposals(client), "overspending") == []


def test_categories_with_payments_get_no_spending_proposal(client, category_ids):
    alquiler = category_ids["Alquiler"]
    history(client, alquiler, 20000, [24000, 19000, 25000])
    client.post(f"/categories/{alquiler}/schedules",
                json={"name": "Alquiler", "amount_cents": 20000, "pattern": "monthly", "day": 1})
    assert by_kind(proposals(client), "overspending") == []


def test_money_with_no_job(client):
    income(client, 21000)
    [p] = by_kind(proposals(client), "unassigned")
    assert p["title"] == "210,00 € with no job yet"
    assert p["href"] == "/budgets"


def test_short_months_grouped(client, category_ids):
    coche = category_ids["Ocio"]
    client.post(f"/categories/{coche}/schedules", json={
        "name": "Seguro", "amount_cents": 50000, "pattern": "some_months", "months": [3, 6]})
    client.post("/income-schedules", json={"name": "Nómina", "amount_cents": 1000,
                                           "pattern": "monthly", "day": 1})
    [p] = by_kind(proposals(client), "short_months")
    assert p["title"] == "March and June won't be fully covered"
    assert p["href"] == "/upcoming?month=2027-03"


def test_late_income_first(client, category_ids, monkeypatch):
    history(client, category_ids["Restaurantes"], 20000, [24000, 19000, 25000])
    client.post("/income-schedules", json={"name": "Nómina", "amount_cents": 280000,
                                           "pattern": "monthly", "day": 5, "payer": "Acme SL"})
    items = proposals(client)
    assert [p["kind"] for p in items][:2] == ["late_income", "overspending"]
    late = items[0]
    assert (late["title"], late["action"], late["payer"]) == (
        "Your Nómina isn't here yet", "add_income", "Acme SL")


# ---- Dismiss and accept -----------------------------------------------------------------


def test_not_now_hides_for_a_week(client, category_ids, monkeypatch):
    history(client, category_ids["Restaurantes"], 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    assert client.post(f"/coach/proposals/{p['fingerprint']}/dismiss").status_code == 204
    assert by_kind(proposals(client), "overspending") == []
    set_today(monkeypatch, date(2026, 10, 20))
    assert by_kind(proposals(client), "overspending") == []
    set_today(monkeypatch, date(2026, 10, 21))
    assert len(by_kind(proposals(client), "overspending")) == 1


def test_accepting_a_raise(client, category_ids):
    restaurantes = category_ids["Restaurantes"]
    income(client, 100000, "2026-07-01")  # money to assign from the start
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    before = client.get("/budget/2026-10").json()["to_be_assigned_cents"]
    assert before > 3000
    income(client, 50000)
    [p] = by_kind(proposals(client), "overspending")
    response = client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={"revision": p["revision"]})
    assert response.status_code == 200, response.text
    budget = client.get("/budget/2026-10").json()
    row = next(c for g in budget["groups"] for c in g["categories"] if c["id"] == restaurantes)
    assert row["assigned_cents"] == 23000
    assert budget["to_be_assigned_cents"] == before + 50000 - 3000
    assert by_kind(response.json()["proposals"], "overspending") == []
    assert by_kind(proposals(client), "overspending") == []


def test_raise_needs_a_source(client, category_ids):
    restaurantes, ocio = category_ids["Restaurantes"], category_ids["Ocio"]
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    client.get("/budget/2026-10")
    income(client, 5000)
    client.put(f"/budget/2026-10/assignments/{ocio}", json={"amount_cents": 4000})
    [p] = by_kind(proposals(client), "overspending")
    assert [s["category_id"] for s in p["sources"]] == [ocio]
    fp = p["fingerprint"]
    refused = client.post(f"/coach/proposals/{fp}/accept", json={"revision": p["revision"]})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "not_enough_to_assign"
    ok = client.post(f"/coach/proposals/{fp}/accept",
                     json={"revision": p["revision"], "from_category_id": ocio})
    assert ok.status_code == 200, ok.text
    budget = client.get("/budget/2026-10").json()
    rows = {c["id"]: c for g in budget["groups"] for c in g["categories"]}
    assert rows[restaurantes]["assigned_cents"] == 23000
    assert rows[ocio]["assigned_cents"] == 1000


def test_lower_frees_money(client, category_ids):
    gasolina = category_ids["Gasolina"]
    history(client, gasolina, 12000, [5500, 6200, 5800])
    before = client.get("/budget/2026-10").json()["to_be_assigned_cents"]
    [p] = by_kind(proposals(client), "underspending")
    assert client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={"revision": p["revision"]}).status_code == 200
    after = client.get("/budget/2026-10").json()
    row = next(c for g in after["groups"] for c in g["categories"] if c["id"] == gasolina)
    assert row["assigned_cents"] == 6000
    assert after["to_be_assigned_cents"] == before + 6000


def test_only_raise_and_lower_are_acceptable(client):
    income(client, 21000)
    [p] = by_kind(proposals(client), "unassigned")
    assert p["revision"] is None  # only raise and lower carry one
    response = client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={"revision": "x"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_acceptable"
    assert client.post("/coach/proposals/nope/dismiss").status_code == 404


def test_state_holds_no_amounts(client, db, user, category_ids):
    history(client, category_ids["Restaurantes"], 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    client.post(f"/coach/proposals/{p['fingerprint']}/dismiss")
    [row] = db.query(CoachProposalState).filter_by(user_id=user.id).all()
    columns = {c.name for c in CoachProposalState.__table__.columns}
    assert columns == {"id", "user_id", "fingerprint", "state", "until", "revision", "created_at"}
    assert row.fingerprint == p["fingerprint"] and "€" not in row.fingerprint


def test_euro_format():
    assert coach.eur(123450) == "1.234,50 €"
    assert coach.round_up(22667) == 23000



# ---- redesign-safety-baseline: F02, F03 ------------------------------------------------


def _budget_row(client, category_id: str) -> dict:
    budget = client.get("/budget/2026-10").json()
    return next(c for g in budget["groups"] for c in g["categories"] if c["id"] == category_id)


def test_a_changed_proposal_is_not_applied(client, category_ids):
    """F02: acceptance applies exactly the reviewed amount, or nothing."""
    restaurantes = category_ids["Restaurantes"]
    income(client, 200000, "2026-07-01")
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    [shown] = by_kind(proposals(client), "overspending")
    assert shown["suggested_cents"] == 23000
    # A forgotten September expense raises the average after it was shown.
    client.post("/transactions", json={"amount_cents": 30000, "category_id": restaurantes,
                                       "date": "2026-09-20"})
    response = client.post(f"/coach/proposals/{shown['fingerprint']}/accept",
                           json={"revision": shown["revision"]})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "proposal_changed"
    assert detail["proposal"]["suggested_cents"] == 33000
    assert _budget_row(client, restaurantes)["assigned_cents"] == 20000


def test_accepting_twice_applies_once(client, category_ids):
    restaurantes = category_ids["Restaurantes"]
    income(client, 200000, "2026-07-01")
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    url, body = f"/coach/proposals/{p['fingerprint']}/accept", {"revision": p["revision"]}
    before = client.get("/budget/2026-10").json()["to_be_assigned_cents"]
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json=body).status_code == 200
    assert _budget_row(client, restaurantes)["assigned_cents"] == 23000
    assert client.get("/budget/2026-10").json()["to_be_assigned_cents"] == before - 3000


def test_accept_requires_a_revision(client, category_ids):
    history(client, category_ids["Restaurantes"], 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    assert client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={}).status_code == 422


def test_a_category_cannot_fund_itself(client, category_ids):
    """F03: the target as its own source changes nothing."""
    restaurantes = category_ids["Restaurantes"]
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    before = client.get("/budget/2026-10").json()
    response = client.post(f"/coach/proposals/{p['fingerprint']}/accept",
                           json={"revision": p["revision"], "from_category_id": restaurantes})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "same_category"
    after = client.get("/budget/2026-10").json()
    assert after["to_be_assigned_cents"] == before["to_be_assigned_cents"]
    assert _budget_row(client, restaurantes)["assigned_cents"] == 20000


def test_a_savings_category_is_not_a_free_source(client, category_ids):
    restaurantes, ahorro = category_ids["Restaurantes"], category_ids["Ahorro"]
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    client.patch(f"/categories/{ahorro}", json={"savings": True})
    income(client, 50000)
    client.put(f"/budget/2026-10/assignments/{ahorro}", json={"amount_cents": 40000})
    [p] = by_kind(proposals(client), "overspending")
    response = client.post(f"/coach/proposals/{p['fingerprint']}/accept",
                           json={"revision": p["revision"], "from_category_id": ahorro})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_enough_in_source"
    assert _budget_row(client, ahorro)["assigned_cents"] == 40000


def test_a_valid_source_keeps_total_assigned(client, category_ids):
    restaurantes, ocio = category_ids["Restaurantes"], category_ids["Ocio"]
    history(client, restaurantes, 20000, [24000, 19000, 25000])
    income(client, 5000)
    client.put(f"/budget/2026-10/assignments/{ocio}", json={"amount_cents": 4000})
    before = client.get("/budget/2026-10").json()
    [p] = by_kind(proposals(client), "overspending")
    client.post(f"/coach/proposals/{p['fingerprint']}/accept",
                json={"revision": p["revision"], "from_category_id": ocio})
    after = client.get("/budget/2026-10").json()
    assert after["to_be_assigned_cents"] == before["to_be_assigned_cents"]
    total = lambda v: sum(c["assigned_cents"] for g in v["groups"] for c in g["categories"])
    assert total(after) == total(before)
