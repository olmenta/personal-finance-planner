"""Debts: engine, API, overview integration, loan conversion
(openspec change debt-paydown)."""

from datetime import date

import pytest

from app import clock
from app.services import debts as engine
from app.services.debts import PlanDebt

TODAY = date(2026, 10, 14)


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    set_today(monkeypatch, TODAY)


def set_today(monkeypatch, today: date) -> None:
    for target in (clock, "app.routers.accounts", "app.services.overview"):
        if target is clock:
            monkeypatch.setattr(clock, "today_madrid", lambda: today)
        else:
            monkeypatch.setattr(f"{target}.today_madrid", lambda: today)


def card(client, name="Sabadell - Visa", owed=63462, **extra) -> str:
    body = {"name": name, "type": "credit", "opening_balance_cents": -owed, **extra}
    response = client.post("/accounts", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def bank(client, name="Banco") -> str:
    return client.post("/accounts", json={"name": name, "type": "bank",
                                          "opening_balance_cents": 500000}).json()["id"]


def add_debt(client, **body) -> dict:
    response = client.post("/debts", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def by_name(view: dict, name: str) -> dict:
    return next(d for d in view["debts"] if d["name"] == name)


# ---- Engine (pure) ----------------------------------------------------------------------


def test_rates_normalize_to_monthly():
    assert engine.monthly_rate(150, "month") == pytest.approx(0.015)
    assert engine.monthly_rate(1800, "year") == pytest.approx(0.015)
    assert engine.monthly_rate(None, None) is None


def test_plan_for_a_target_month():
    assert engine.plan_for_target(63462, 0.015, 4) == 16465
    assert engine.plan_for_target(63462, None, 4) == 15866


def test_card_with_interest_ends_in_the_fourth_payment():
    debt = PlanDebt(id="c", kind="card", owed=63462, rate=0.015,
                    required={m: 20000 for m in range(120)}, roll_cents=20000)
    engine.simulate([debt], 0, 0)
    assert debt.end_index == 3


def test_paid_off_debt_rolls_its_money_forward():
    visa = PlanDebt(id="c", kind="card", owed=63462, rate=0.015,
                    required={m: 20000 for m in range(120)}, roll_cents=20000)
    family = PlanDebt(id="p", kind="personal", owed=290000, rate=None, interest_free=True)
    engine.simulate([visa, family], 10000, 0)
    assert visa.end_index == 2
    # From month 3 the family debt gets 200 € plan + 100 € extra a month.
    assert family.end_index == 11


def test_undated_personal_debt_never_ends_without_extra():
    family = PlanDebt(id="p", kind="personal", owed=290000, rate=None, interest_free=True)
    engine.simulate([family], 0, 0)
    assert family.end_index is None


def test_order_highest_rate_then_unknown_then_interest_free():
    debts = [
        PlanDebt("p", "personal", 100, None, interest_free=True),
        PlanDebt("u", "loan", 50, None),
        PlanDebt("l", "loan", 500, 0.07 / 12),
        PlanDebt("c", "card", 900, 0.015),
    ]
    assert [d.id for d in engine.order(debts)] == ["c", "l", "u", "p"]


def test_tie_goes_to_smallest_balance():
    debts = [PlanDebt("big", "loan", 900, None), PlanDebt("small", "loan", 100, None)]
    assert [d.id for d in engine.order(debts)] == ["small", "big"]


# ---- API --------------------------------------------------------------------------------


def test_loan_balance_from_installments(client):
    view = add_debt(client, kind="loan", name="Préstamo BBVA", installment_cents=29017,
                    installments_left=34, next_month="2026-10", day=2)
    loan = by_name(view, "Préstamo BBVA")
    assert (loan["owed_cents"], loan["end_month"], loan["installments_left"]) == (
        986578, "2029-07", 34)
    assert loan["required_monthly_cents"] == 29017


def test_card_debt_is_what_is_not_set_aside(client):
    account = card(client)
    view = add_debt(client, kind="card", account_id=account, plan_monthly_cents=20000,
                    rate_bp=150, rate_period="month")
    visa = by_name(view, "Sabadell - Visa")
    assert visa["owed_cents"] == 63462
    assert visa["monthly_interest_cents"] == 952
    assert visa["end_month"] == "2027-01"
    assert visa["plan_monthly_cents"] == 20000


def test_card_plan_from_a_target_month(client):
    account = card(client)
    view = add_debt(client, kind="card", account_id=account, target_month="2027-01")
    assert by_name(view, "Sabadell - Visa")["plan_monthly_cents"] == 15866


def test_card_plan_below_the_minimum_is_flagged(client):
    account = card(client)
    view = add_debt(client, kind="card", account_id=account, plan_monthly_cents=5000,
                    minimum_cents=6000)
    assert by_name(view, "Sabadell - Visa")["below_minimum"] is True


def test_minimum_skipped(client):
    view = add_debt(client, kind="card", account_id=card(client), plan_monthly_cents=5000)
    assert by_name(view, "Sabadell - Visa")["below_minimum"] is None


def test_second_debt_on_the_same_card_is_409(client):
    account = card(client)
    add_debt(client, kind="card", account_id=account, plan_monthly_cents=5000)
    response = client.post("/debts", json={"kind": "card", "account_id": account,
                                           "plan_monthly_cents": 6000})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "debt_exists"


def test_invalid_debt_is_422(client):
    response = client.post("/debts", json={"kind": "card", "account_id": "x"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_debt"


def test_personal_debt_goes_down_as_it_is_paid(client):
    view = add_debt(client, kind="personal", name="Jose y Ruby", owed_cents=290000,
                    lender="Jose y Ruby")
    category_id = by_name(view, "Jose y Ruby")["category_id"]
    client.post("/transactions", json={"amount_cents": 40000, "category_id": category_id,
                                       "date": "2026-10-14"})
    debt = by_name(client.get("/debts").json(), "Jose y Ruby")
    assert debt["owed_cents"] == 250000
    assert debt["lender"] == "Jose y Ruby"
    assert debt["end_month"] is None  # no date, no extra


def test_personal_debt_with_a_due_month_is_required(client):
    view = add_debt(client, kind="personal", name="Jose y Ruby", owed_cents=290000,
                    due_month="2027-03")
    debt = by_name(view, "Jose y Ruby")
    schedules = client.get(f"/categories/{debt['category_id']}/schedules").json()
    assert [(s["pattern"], s["once_month"], s["amount_cents"]) for s in schedules] == [
        ("once", "2027-03", 290000)]
    assert debt["end_month"] == "2027-03"
    assert debt["required_monthly_cents"] > 0  # the catch-up set aside each month


def test_order_and_extra_target(client):
    add_debt(client, kind="personal", name="Jose y Ruby", owed_cents=290000)
    add_debt(client, kind="loan", name="Ikea", installment_cents=4500, installments_left=10,
             next_month="2026-10", rate_bp=700, rate_period="year")
    add_debt(client, kind="card", account_id=card(client), plan_monthly_cents=20000,
             rate_bp=150, rate_period="month")
    view = client.put("/debts/extra", json={"extra_monthly_cents": 10000}).json()
    assert [d["name"] for d in view["debts"]] == ["Sabadell - Visa", "Ikea", "Jose y Ruby"]
    assert [d["position"] for d in view["debts"]] == [1, 2, 3]
    assert view["extra_target_debt_id"] == view["debts"][0]["id"]
    assert view["extra_monthly_cents"] == 10000
    assert view["debt_free_month"] is not None  # the extra eventually reaches the family debt


def test_delete_keeps_the_category(client, category_ids):
    view = add_debt(client, kind="loan", name="Ikea", installment_cents=4500,
                    installments_left=10, next_month="2026-10")
    debt = by_name(view, "Ikea")
    assert client.delete(f"/debts/{debt['id']}").status_code == 204
    names = {c["name"] for g in client.get("/categories").json() for c in g["categories"]}
    assert "Ikea" in names
    assert client.get(f"/categories/{debt['category_id']}/schedules").json() == []


def test_patch_rewrites_the_loan_schedule(client):
    debt = by_name(add_debt(client, kind="loan", name="Ikea", installment_cents=4500,
                            installments_left=10, next_month="2026-10"), "Ikea")
    view = client.patch(f"/debts/{debt['id']}", json={"installments_left": 4}).json()
    assert by_name(view, "Ikea")["owed_cents"] == 4 * 4500
    wrong = client.patch(f"/debts/{debt['id']}", json={"owed_cents": 1})
    assert wrong.status_code == 422


def test_cushion_suggestion(client):
    view = add_debt(client, kind="loan", name="Ikea", installment_cents=4500,
                    installments_left=10, next_month="2026-10")
    assert view["cushion"] == {"suggested_cents": 30000, "saved_cents": 0}


def test_debt_schedules_are_managed_from_debts(client):
    debt = by_name(add_debt(client, kind="loan", name="Ikea", installment_cents=4500,
                            installments_left=10, next_month="2026-10"), "Ikea")
    [schedule] = client.get(f"/categories/{debt['category_id']}/schedules").json()
    assert schedule["debt_id"] == debt["id"]
    response = client.patch(f"/schedules/{schedule['id']}", json={"amount_cents": 1})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "managed_by_debt"
    assert client.delete(f"/schedules/{schedule['id']}").status_code == 409


def test_payment_category_holds_one_plan(client):
    account = card(client)
    payment = next(a for a in client.get("/accounts").json() if a["id"] == account)
    category = payment["payment_category_id"]
    body = {"name": "x", "amount_cents": 100, "pattern": "monthly"}
    assert client.post(f"/categories/{category}/schedules", json=body).status_code == 201
    response = client.post(f"/categories/{category}/schedules", json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "card_plan_exists"


# ---- Overview, plan and conversion ------------------------------------------------------


def test_card_plan_sets_assignment_and_counts_in_the_plan(client):
    account = card(client)
    view = add_debt(client, kind="card", account_id=account, plan_monthly_cents=20000)
    category = by_name(view, "Sabadell - Visa")["category_id"]
    budget = client.get("/budget/2026-10").json()
    payment = next(c for g in budget["groups"] for c in g["categories"] if c["id"] == category)
    assert payment["assigned_cents"] == 20000
    put = client.put(f"/budget/2026-10/assignments/{category}", json={"amount_cents": 1})
    assert put.json()["detail"]["code"] == "assignment_from_payments"
    assert client.get("/plan/summary?from=2026-10").json()["scheduled_cents"] >= 12 * 20000


def test_card_plan_pending_then_paid_by_a_transfer(client):
    account = card(client, payment_day=30)
    source = bank(client)
    add_debt(client, kind="card", account_id=account, plan_monthly_cents=20000)
    pending = client.get("/overview/2026-10").json()["to_pay"]
    assert [p["name"] for p in pending] == ["Debt plan"]
    client.post("/transfers", json={"from_account_id": source, "to_account_id": account,
                                    "amount_cents": 45000, "date": "2026-10-14"})
    overview = client.get("/overview/2026-10").json()
    assert overview["to_pay"] == []
    assert "Debt plan" in [p["name"] for p in overview["paid"]["items"]]


def test_installment_late_after_three_days(client, monkeypatch):
    add_debt(client, kind="loan", name="Ikea", installment_cents=4500, installments_left=10,
             next_month="2026-10", day=5)
    set_today(monkeypatch, date(2026, 10, 8))
    [entry] = client.get("/overview/2026-10").json()["to_pay"]
    assert entry["late"] is False
    set_today(monkeypatch, date(2026, 10, 9))
    [entry] = client.get("/overview/2026-10").json()["to_pay"]
    assert entry["late"] is True


def test_non_debt_payment_is_never_late(client, category_ids, monkeypatch):
    client.post(f"/categories/{category_ids['Alquiler']}/schedules",
                json={"name": "Alquiler", "amount_cents": 95200, "pattern": "monthly", "day": 1})
    [entry] = client.get("/overview/2026-10").json()["to_pay"]
    assert entry["late"] is False


def test_convert_a_loan_set_up_as_a_card(client):
    account = card(client, name="Sabadell - Prestamo", owed=970983, payment_day=2)
    payment = next(a for a in client.get("/accounts").json() if a["id"] == account)
    source = bank(client)
    # Money already set aside for it moves to the new loan category.
    client.post("/budget/2026-10/moves", json={"from_category_id": None,
                                                "to_category_id": payment["payment_category_id"],
                                                "amount_cents": 29017})
    response = client.post(f"/accounts/{account}/convert-to-loan", json={
        "installment_cents": 29017, "installments_left": 34, "next_month": "2026-11", "day": 2})
    assert response.status_code == 200, response.text
    loan = by_name(response.json(), "Sabadell - Prestamo")
    assert (loan["kind"], loan["installments_left"], loan["next_month"]) == ("loan", 34, "2026-11")
    accounts = {a["id"]: a for a in client.get("/accounts").json()}
    assert accounts[account]["archived"] is True
    budget = client.get("/budget/2026-10").json()
    moved = next(c for g in budget["groups"] for c in g["categories"] if c["id"] == loan["category_id"])
    assert moved["available_cents"] >= 29017
    assert source in accounts


def test_only_credit_accounts_convert(client):
    response = client.post(f"/accounts/{bank(client)}/convert-to-loan", json={
        "installment_cents": 100, "installments_left": 1, "next_month": "2026-11"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_convertible"


def test_setting_the_plan_aside_does_not_pay_the_debt(client):
    account = card(client)
    source = bank(client)
    add_debt(client, kind="card", account_id=account, plan_monthly_cents=20000)
    assert by_name(client.get("/debts").json(), "Sabadell - Visa")["owed_cents"] == 63462
    client.post("/transfers", json={"from_account_id": source, "to_account_id": account,
                                    "amount_cents": 20000, "date": "2026-10-14"})
    assert by_name(client.get("/debts").json(), "Sabadell - Visa")["owed_cents"] == 43462
