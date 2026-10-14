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
    response = client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={})
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
    refused = client.post(f"/coach/proposals/{fp}/accept", json={})
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "not_enough_to_assign"
    ok = client.post(f"/coach/proposals/{fp}/accept", json={"from_category_id": ocio})
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
    assert client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={}).status_code == 200
    after = client.get("/budget/2026-10").json()
    row = next(c for g in after["groups"] for c in g["categories"] if c["id"] == gasolina)
    assert row["assigned_cents"] == 6000
    assert after["to_be_assigned_cents"] == before + 6000


def test_only_raise_and_lower_are_acceptable(client):
    income(client, 21000)
    [p] = by_kind(proposals(client), "unassigned")
    response = client.post(f"/coach/proposals/{p['fingerprint']}/accept", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_acceptable"
    assert client.post("/coach/proposals/nope/dismiss").status_code == 404


def test_state_holds_no_amounts(client, db, user, category_ids):
    history(client, category_ids["Restaurantes"], 20000, [24000, 19000, 25000])
    [p] = by_kind(proposals(client), "overspending")
    client.post(f"/coach/proposals/{p['fingerprint']}/dismiss")
    [row] = db.query(CoachProposalState).filter_by(user_id=user.id).all()
    columns = {c.name for c in CoachProposalState.__table__.columns}
    assert columns == {"id", "user_id", "fingerprint", "state", "until", "created_at"}
    assert row.fingerprint == p["fingerprint"] and "€" not in row.fingerprint


def test_euro_format():
    assert coach.eur(123450) == "1.234,50 €"
    assert coach.round_up(22667) == 23000


