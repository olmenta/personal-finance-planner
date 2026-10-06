"""Income schedules: CRUD, expected versus received, linking, migration
(openspec change income-schedules)."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

from app import clock
from app.models import IncomeSchedule, Payee, UserPreferences
from app.services.payees import delete_orphan_payees


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    set_today(monkeypatch, date(2026, 10, 14))


def set_today(monkeypatch, today: date) -> None:
    monkeypatch.setattr(clock, "today_madrid", lambda: today)


def add_income(client, **body) -> dict:
    body = {"name": "Nómina", "amount_cents": 280000, "pattern": "monthly", **body}
    response = client.post("/income-schedules", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def inflow(client, amount_cents: int, day: str, payee: str | None = None) -> dict:
    body = {"amount_cents": amount_cents, "kind": "income", "date": day}
    if payee is not None:
        body["payee"] = payee
    response = client.post("/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def month(client, m: str = "2026-10") -> dict:
    response = client.get(f"/income/{m}")
    assert response.status_code == 200, response.text
    return response.json()


def occurrence(view: dict, name: str) -> dict:
    return next(o for o in view["occurrences"] if o["name"] == name)


# ---- CRUD -------------------------------------------------------------------------------


def test_fourteen_payments_a_year(client):
    add_income(client, payer="Acme SL", amount_cents=200000, day=27)
    add_income(client, name="Paga extra", payer="Acme SL", amount_cents=200000,
               pattern="some_months", months=[6, 12], day=20)
    assert month(client, "2027-06")["expected_cents"] == 400000
    assert month(client, "2027-05")["expected_cents"] == 200000
    yearly = {s["name"]: s["yearly_cents"] for s in client.get("/income-schedules").json()}
    assert yearly == {"Paga extra": 400000, "Nómina": 2400000}


def test_undated_income_rejected(client):
    response = client.post("/income-schedules", json={
        "name": "Freelance", "amount_cents": 50000, "pattern": "no_date"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_schedule"


def test_schedules_dont_touch_the_budget(client):
    before = client.get("/budget/2026-10").json()
    add_income(client, amount_cents=200000, day=27)
    after = client.get("/budget/2026-10").json()
    assert after["income_cents"] == before["income_cents"]
    assert after["to_be_assigned_cents"] == before["to_be_assigned_cents"]


def test_payer_resolved_to_an_existing_payee(client, db, user):
    existing = inflow(client, 1000, "2026-09-02", payee="Acme SL")
    schedule = add_income(client, payer="ACME SL")
    assert schedule["payee_id"] == existing["payee_id"]
    assert db.query(Payee).filter_by(user_id=user.id).count() == 1
    assert client.get("/income-schedules").json()[0]["payer"] == "Acme SL"


def test_payer_created_before_any_income(client):
    schedule = add_income(client, name="Alquiler piso", payer="Inquilino Piso")
    payees = {p["name"]: p["id"] for p in client.get("/payees").json()}
    assert payees["Inquilino Piso"] == schedule["payee_id"]


def test_patch_switches_pattern_and_clears_payer(client):
    schedule = add_income(client, payer="Acme SL", day=27)
    response = client.patch(f"/income-schedules/{schedule['id']}", json={
        "pattern": "annual", "month": 12, "payer": ""})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["pattern"], body["month"], body["payer"], body["payee_id"], body["day"]) == (
        "annual", 12, None, None, 27)


def test_unknown_or_foreign_schedule_404(client):
    response = client.patch("/income-schedules/nope", json={"amount_cents": 1})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "income_schedule_not_found"
    assert client.delete("/income-schedules/nope").status_code == 404


def test_list_ordered_by_day_missing_last(client):
    add_income(client, name="Sin día")
    add_income(client, name="Día 27", day=27)
    add_income(client, name="Día 1", day=1)
    assert [s["name"] for s in client.get("/income-schedules").json()] == [
        "Día 1", "Día 27", "Sin día"]


# ---- Matching ---------------------------------------------------------------------------


def test_salary_arrives_a_little_lower(client, monkeypatch):
    set_today(monkeypatch, date(2026, 10, 28))
    add_income(client, payer="Acme SL", day=27)
    txn = inflow(client, 275000, "2026-10-27", payee="ACME SL")
    occ = occurrence(month(client), "Nómina")
    assert (occ["status"], occ["received_cents"], occ["difference_cents"]) == (
        "received", 275000, -5000)
    assert occ["transaction_ids"] == [txn["id"]]


def test_salary_and_extra_pay_in_one_transfer(client):
    add_income(client, payer="Acme SL", amount_cents=200000, day=27)
    add_income(client, name="Paga extra", payer="Acme SL", amount_cents=200000,
               pattern="some_months", months=[6, 12], day=20)
    inflow(client, 400000, "2026-06-25", payee="Acme SL")
    view = month(client, "2026-06")
    assert [(o["name"], o["status"], o["difference_cents"]) for o in view["occurrences"]] == [
        ("Paga extra", "received", 0), ("Nómina", "received", 0)]
    assert view["unplanned"] == []


def test_late_versus_pending(client, monkeypatch):
    add_income(client, payer="Acme SL", day=27)
    set_today(monkeypatch, date(2026, 10, 30))  # 3 days past: still within the grace
    assert occurrence(month(client), "Nómina")["status"] == "pending"
    set_today(monkeypatch, date(2026, 10, 31))
    assert occurrence(month(client), "Nómina")["status"] == "late"


def test_past_month_without_income_is_missed(client):
    add_income(client, day=27)
    assert occurrence(month(client, "2026-09"), "Nómina")["status"] == "missed"
    assert occurrence(month(client, "2026-11"), "Nómina")["status"] == "pending"


def test_missing_day_is_never_late_before_month_end(client, monkeypatch):
    add_income(client)
    set_today(monkeypatch, date(2026, 10, 31))
    assert occurrence(month(client), "Nómina")["status"] == "pending"


def test_matching_by_amount_without_payer(client):
    add_income(client, name="Alquiler piso", amount_cents=120000)
    inflow(client, 118000, "2026-10-05")
    occ = occurrence(month(client), "Alquiler piso")
    assert (occ["status"], occ["difference_cents"]) == ("received", -2000)


def test_amount_outside_tolerance_is_unplanned(client):
    add_income(client, name="Alquiler piso", amount_cents=120000)
    txn = inflow(client, 100000, "2026-10-05")
    view = month(client)
    assert occurrence(view, "Alquiler piso")["status"] == "pending"
    assert [u["transaction_id"] for u in view["unplanned"]] == [txn["id"]]


def test_second_inflow_from_same_payer_is_unplanned(client):
    add_income(client, payer="Acme SL", day=1)
    inflow(client, 280000, "2026-10-01", payee="Acme SL")
    bonus = inflow(client, 90000, "2026-10-10", payee="Acme SL")
    view = month(client)
    assert occurrence(view, "Nómina")["difference_cents"] == 0
    assert [(u["transaction_id"], u["label"]) for u in view["unplanned"]] == [
        (bonus["id"], "Acme SL")]


def test_opening_balance_is_received_but_never_matched(client):
    add_income(client, name="Alquiler piso", amount_cents=120000)
    client.post("/accounts", json={"name": "Sabadell", "type": "bank",
                                   "opening_balance_cents": 120000})
    view = month(client)
    assert occurrence(view, "Alquiler piso")["status"] == "pending"
    assert view["unplanned"] == []
    assert view["received_cents"] == 0


def test_mid_month_contract(client):
    add_income(client, name="Pensión", amount_cents=90000, payer="INSS", day=1)
    add_income(client, payer="Acme SL", day=27)
    inflow(client, 90000, "2026-10-01", payee="INSS")
    view = month(client)
    assert (view["expected_cents"], view["received_cents"], view["still_expected_cents"]) == (
        370000, 90000, 280000)
    assert [(o["name"], o["status"]) for o in view["occurrences"]] == [
        ("Pensión", "received"), ("Nómina", "pending")]
    assert view["has_schedules"] is True


def test_no_schedules(client):
    txn = inflow(client, 240000, "2026-10-02")
    view = month(client)
    assert view["has_schedules"] is False and view["occurrences"] == []
    assert [u["transaction_id"] for u in view["unplanned"]] == [txn["id"]]


# ---- Linking ----------------------------------------------------------------------------


def test_link_once_matched_forever(client):
    schedule = add_income(client, name="Alquiler piso", amount_cents=90000)
    txn = inflow(client, 118000, "2026-10-03", payee="Inquilino Piso")
    assert occurrence(month(client), "Alquiler piso")["status"] == "pending"

    # "This is…": the schedule takes the inflow's payee.
    response = client.patch(f"/income-schedules/{schedule['id']}", json={"payer": "Inquilino Piso"})
    assert response.json()["payee_id"] == txn["payee_id"]
    assert occurrence(month(client), "Alquiler piso")["status"] == "received"

    inflow(client, 118000, "2026-11-03", payee="Inquilino Piso")
    assert occurrence(month(client, "2026-11"), "Alquiler piso")["status"] == "received"


def test_link_by_setting_the_transaction_payee(client):
    add_income(client, payer="Acme SL", day=27)
    txn = inflow(client, 150000, "2026-10-12")  # amount far off, no payee: unplanned
    assert len(month(client)["unplanned"]) == 1
    client.patch(f"/transactions/{txn['id']}", json={"payee": "Acme SL"})
    view = month(client)
    assert view["unplanned"] == []
    assert occurrence(view, "Nómina")["difference_cents"] == -130000


# ---- Payees and migration ---------------------------------------------------------------


def test_schedule_referenced_payee_survives_orphan_cleanup(client, db, user):
    schedule = add_income(client, payer="Acme SL")
    assert delete_orphan_payees(db, user.id, {schedule["payee_id"]}) == 0
    assert db.get(Payee, schedule["payee_id"]) is not None


def _migration():
    path = Path(__file__).parents[1] / "alembic/versions/c5d2e8f1a9b4_income_schedules.py"
    spec = importlib.util.spec_from_file_location("income_schedules_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _preferences(db, user, income: dict) -> None:
    db.add(UserPreferences(user_id=user.id, preferences={"income": income}, prompt_version="v2"))
    db.flush()


def test_migration_converts_expected_income(db, user):
    _preferences(db, user, {"expected_monthly_cents": 470000, "income_day": 27})
    _migration().migrate_expected_income(db.connection())
    [schedule] = db.query(IncomeSchedule).filter_by(user_id=user.id).all()
    assert (schedule.name, schedule.amount_cents, schedule.pattern, schedule.day,
            schedule.payee_id) == ("Monthly income", 470000, "monthly", 27, None)


@pytest.mark.parametrize("income", [{}, {"expected_monthly_cents": 0},
                                    {"expected_monthly_cents": "lots"}])
def test_migration_skips_missing_or_invalid_income(db, user, income):
    _preferences(db, user, income)
    _migration().migrate_expected_income(db.connection())
    assert db.query(IncomeSchedule).filter_by(user_id=user.id).count() == 0


def test_migration_is_idempotent(db, user):
    _preferences(db, user, {"expected_monthly_cents": 470000})
    migration = _migration()
    migration.migrate_expected_income(db.connection())
    migration.migrate_expected_income(db.connection())
    [schedule] = db.query(IncomeSchedule).filter_by(user_id=user.id).all()
    assert schedule.day is None
