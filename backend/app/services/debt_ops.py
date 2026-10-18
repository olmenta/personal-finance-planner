"""Writing debts: one path for the debts API, the accounts conversion, the
coach and, through the API, the dev MCP server (coach-debts-setup design
D1). Validation from plain data lives here; the debt rules stay in
services/debts.py."""

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Debt, User
from ..schemas import ConvertToLoanIn, DebtIn, DebtUpdate, horizon_error
from . import debts as service
from .debts import DebtError

_create: TypeAdapter = TypeAdapter(DebtIn)


def _code(exc: ValidationError) -> str:
    return "outside_planning_horizon" if horizon_error(exc) else "invalid_debt"


def debt_or_404(db: Session, user: User, debt_id: str) -> Debt:
    debt = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if debt is None:
        raise DebtError(404, "debt_not_found")
    return debt


def create(db: Session, user: User, body: dict) -> Debt:
    try:
        valid = _create.validate_python(body)
    except ValidationError as exc:
        raise DebtError(422, _code(exc)) from exc
    return service.create_debt(db, user, valid)


def update(db: Session, user: User, debt_id: str, changes: dict) -> Debt:
    debt = debt_or_404(db, user, debt_id)
    try:
        valid = DebtUpdate.model_validate(changes)
    except ValidationError as exc:
        raise DebtError(422, _code(exc)) from exc
    return service.update_debt(db, user, debt, valid)


def delete(db: Session, user: User, debt_id: str) -> None:
    service.delete_debt(db, user, debt_or_404(db, user, debt_id))


def set_extra(db: Session, user: User, cents: int) -> int:
    """Set the monthly extra; returns the previous one."""
    if cents < 0:
        raise DebtError(422, "invalid_debt")
    settings = service.settings(db, user)
    previous = settings.extra_monthly_cents
    settings.extra_monthly_cents = cents
    db.flush()
    return previous


def convert(db: Session, user: User, account_id: str, body: dict) -> Debt:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise DebtError(404, "account_not_found")
    try:
        valid = ConvertToLoanIn.model_validate(body)
    except ValidationError as exc:
        raise DebtError(422, _code(exc)) from exc
    return service.convert_to_loan(db, user, account, valid)


def view_row(db: Session, user: User, debt_id: str):
    """The debt as the debts view reports it now (owed, installments left…)."""
    return next((d for d in service.build_debts_view(db, user).debts if d.id == debt_id), None)


def fields_of(db: Session, user: User, debt: Debt) -> dict:
    """What `create` needs to recreate the debt as it is now (for undo)."""
    row = view_row(db, user, debt.id)
    rate = {"rate_bp": debt.rate_bp, "rate_period": debt.rate_period} if debt.rate_bp is not None else {}
    if debt.kind == "card":
        body = {"kind": "card", "account_id": row.account_id, "plan_monthly_cents": row.plan_monthly_cents,
                "minimum_cents": debt.minimum_cents}
    elif debt.kind == "loan":
        body = {"kind": "loan", "name": row.name, "installment_cents": row.installment_cents,
                "installments_left": row.installments_left, "next_month": row.next_month, "day": row.day}
    else:
        body = {"kind": "personal", "name": row.name, "owed_cents": row.owed_cents,
                "due_month": row.due_month, "lender": row.lender}
    return {k: v for k, v in {**body, **rate}.items() if v is not None}
