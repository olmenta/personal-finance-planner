"""The shared debt operation (openspec change coach-debts-setup, debts
"One shared debt operation")."""

from datetime import date

import pytest

from app import clock
from app.services import debt_ops
from app.services.debts import DebtError


@pytest.fixture(autouse=True)
def mid_october(monkeypatch):
    today = date(2026, 10, 14)
    monkeypatch.setattr(clock, "today_madrid", lambda: today)
    monkeypatch.setattr("app.routers.accounts.today_madrid", lambda: today)
    monkeypatch.setattr("app.services.overview.today_madrid", lambda: today)


def card(client, owed=63462) -> str:
    return client.post("/accounts", json={"name": "Visa", "type": "credit", "opening_balance_cents": -owed}).json()["id"]


def recreated(db, user, debt) -> dict:
    """Delete the debt and create it again from `fields_of`: its view row."""
    fields = debt_ops.fields_of(db, user, debt)
    before = debt_ops.view_row(db, user, debt.id).model_dump(exclude={"id", "position"})
    debt_ops.delete(db, user, debt.id)
    again = debt_ops.create(db, user, fields)
    after = debt_ops.view_row(db, user, again.id).model_dump(exclude={"id", "position"})
    return before, after


def test_card_recreates_with_its_plan(client, db, user):
    debt = debt_ops.create(db, user, {"kind": "card", "account_id": card(client), "target_month": "2027-01",
                                      "rate_bp": 150, "rate_period": "month", "minimum_cents": 3000})
    fields = debt_ops.fields_of(db, user, debt)
    assert fields["plan_monthly_cents"] == debt_ops.view_row(db, user, debt.id).plan_monthly_cents
    assert "target_month" not in fields
    before, after = recreated(db, user, debt)
    assert before == after


def test_loan_recreates_with_installments_left(client, db, user):
    debt = debt_ops.create(db, user, {"kind": "loan", "name": "Ikea", "installment_cents": 4500,
                                      "installments_left": 10, "next_month": "2026-11", "day": 5})
    before, after = recreated(db, user, debt)
    assert before == after and after["installments_left"] == 10


def test_personal_recreates_with_owed_now(client, db, user):
    debt = debt_ops.create(db, user, {"kind": "personal", "name": "Hermano", "owed_cents": 67000,
                                      "lender": "Juan"})
    before, after = recreated(db, user, debt)
    assert before == after and after["lender"] == "Juan"


def test_set_extra_returns_the_previous_value(db, user):
    assert debt_ops.set_extra(db, user, 10000) == 0
    assert debt_ops.set_extra(db, user, 5000) == 10000


def test_invalid_input_and_duplicates(client, db, user):
    with pytest.raises(DebtError) as invalid:
        debt_ops.create(db, user, {"kind": "loan", "name": "X"})
    assert invalid.value.code == "invalid_debt"
    account = card(client)
    debt_ops.create(db, user, {"kind": "card", "account_id": account, "plan_monthly_cents": 20000})
    with pytest.raises(DebtError) as dup:
        debt_ops.create(db, user, {"kind": "card", "account_id": account, "plan_monthly_cents": 10000})
    assert dup.value.code == "debt_exists"
