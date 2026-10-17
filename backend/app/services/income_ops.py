"""Writing expected income (income schedules) and linking an inflow to its
schedule: one path for the income API, the coach and, through the API, the
dev MCP server (coach-income-setup design D1). Income schedules never touch
the budget; these writes only change the plan and the matching."""

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import IncomeSchedule, Transaction, User
from ..schemas import SCHEDULE_FIELDS, IncomeScheduleIn, horizon_error
from .income import apply_schedule
from .payees import resolve_payee

_validator: TypeAdapter = TypeAdapter(IncomeScheduleIn)

PATTERN_FIELDS = {
    "monthly": {"count", "start_month"},
    "some_months": {"months"},
    "annual": {"month"},
    "every_n": {"every_n", "start_month"},
    "once": {"once_month"},
}
COMMON_FIELDS = {"name", "amount_cents", "pattern", "day", "estimated", "payer"}


class IncomeError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def validate(body: dict):
    try:
        return _validator.validate_python(body)
    except ValidationError as exc:
        raise IncomeError(422, "outside_planning_horizon" if horizon_error(exc) else "invalid_schedule") from exc


def fields_of(schedule: IncomeSchedule) -> dict:
    """The income's rule fields and payer name, as stored."""
    return {f: getattr(schedule, f) for f in SCHEDULE_FIELDS} | {"payer": schedule.payer}


def merged_fields(current: dict, changes: dict) -> dict:
    """`changes` over `current`, keeping only the resulting pattern's fields;
    an explicit empty payer clears it."""
    merged = current | changes
    if "payer" in changes and changes["payer"] is None:
        merged["payer"] = ""
    keep = COMMON_FIELDS | PATTERN_FIELDS.get(merged.get("pattern"), set())
    return {k: v for k, v in merged.items() if k in keep and v is not None}


def schedule_or_404(db: Session, user: User, schedule_id: str) -> IncomeSchedule:
    schedule = db.scalar(
        select(IncomeSchedule).where(IncomeSchedule.id == schedule_id, IncomeSchedule.user_id == user.id)
    )
    if schedule is None:
        raise IncomeError(404, "income_schedule_not_found")
    return schedule


def create_income(db: Session, user: User, body: dict) -> IncomeSchedule:
    valid = validate(body)
    schedule = IncomeSchedule(user_id=user.id)
    apply_schedule(db, user.id, schedule, valid)
    db.add(schedule)
    db.flush()
    return schedule


def update_income(db: Session, user: User, schedule_id: str, changes: dict) -> IncomeSchedule:
    """Partial update: merged onto the stored row, then re-validated whole."""
    schedule = schedule_or_404(db, user, schedule_id)
    apply_schedule(db, user.id, schedule, validate(merged_fields(fields_of(schedule), changes)))
    db.flush()
    return schedule


def delete_income(db: Session, user: User, schedule_id: str) -> None:
    db.delete(schedule_or_404(db, user, schedule_id))
    db.flush()


def inflow_or_404(db: Session, user: User, transaction_id: str) -> Transaction:
    """A confirmed, uncategorized, positive transaction of the user that isn't
    a transfer twin or an opening balance (the income-inflow rule)."""
    txn = db.scalar(select(Transaction).where(
        Transaction.id == transaction_id, Transaction.user_id == user.id, Transaction.status == "confirmed",
        Transaction.category_id.is_(None), Transaction.amount_cents > 0,
        Transaction.transfer_pair_id.is_(None), Transaction.source != "opening_balance",
    ))
    if txn is None:
        raise IncomeError(404, "transaction_not_found")
    return txn


def link_income(db: Session, user: User, transaction_id: str, schedule_id: str) -> None:
    """Link an inflow to a schedule through payer equality (income-schedules,
    "Linking unplanned income"): the schedule's payee goes to the inflow; or
    the inflow's payee to the schedule; or the schedule's name becomes a
    payee for both. Later inflows from that payee then match by themselves."""
    txn = inflow_or_404(db, user, transaction_id)
    schedule = schedule_or_404(db, user, schedule_id)
    if schedule.payee_id:
        txn.payee_id = schedule.payee_id
    elif txn.payee_id:
        schedule.payee_id = txn.payee_id
    else:
        payee = resolve_payee(db, user.id, schedule.name)
        schedule.payee_id = payee.id
        txn.payee_id = payee.id
    db.flush()
    db.refresh(schedule)
    db.refresh(txn)
