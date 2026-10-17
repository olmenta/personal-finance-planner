"""Writing payments (payment schedules): one path for the schedules API, the
coach and, through the API, the dev MCP server (coach-payments-setup design
D1). Validation, the debt and card-plan guards, the planning horizon and the
computed-assignment refresh live here, so the rules can't drift."""

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, PaymentSchedule, User
from ..schemas import SCHEDULE_FIELDS, ScheduleIn, horizon_error
from .budget_view import refresh_computed_assignments
from .debts import debt_for_category

_validator: TypeAdapter = TypeAdapter(ScheduleIn)

# Fields each pattern keeps; switching pattern drops the others.
PATTERN_FIELDS = {
    "monthly": {"count", "start_month"},
    "some_months": {"months"},
    "annual": {"month"},
    "every_n": {"every_n", "start_month"},
    "once": {"once_month"},
    "no_date": set(),
}
COMMON_FIELDS = {"name", "amount_cents", "pattern", "day", "estimated"}


class PaymentError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def validate(body: dict):
    try:
        return _validator.validate_python(body)
    except ValidationError as exc:
        raise PaymentError(422, "outside_planning_horizon" if horizon_error(exc) else "invalid_schedule") from exc


def fields_of(schedule: PaymentSchedule) -> dict:
    """The payment's rule fields, as stored (for previews, results and undo)."""
    return {f: getattr(schedule, f) for f in SCHEDULE_FIELDS}


def _apply(schedule: PaymentSchedule, valid) -> None:
    data = valid.model_dump()
    for field in SCHEDULE_FIELDS:
        setattr(schedule, field, data.get(field))
    if schedule.estimated is None:
        schedule.estimated = False


def category_or_404(db: Session, user: User, category_id: str) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if category is None:
        raise PaymentError(404, "category_not_found")
    return category


def schedule_or_404(db: Session, user: User, schedule_id: str) -> PaymentSchedule:
    schedule = db.scalar(
        select(PaymentSchedule).where(PaymentSchedule.id == schedule_id, PaymentSchedule.user_id == user.id)
    )
    if schedule is None:
        raise PaymentError(404, "schedule_not_found")
    return schedule


def not_managed(db: Session, category_id: str) -> None:
    """Debt schedules are written only through the debts API (debts design D4)."""
    if debt_for_category(db, category_id) is not None:
        raise PaymentError(409, "managed_by_debt")


def merged_fields(current: dict, changes: dict) -> dict:
    """`changes` over `current`, keeping only the fields of the resulting
    pattern (a partial update, before validation)."""
    merged = current | changes
    keep = COMMON_FIELDS | PATTERN_FIELDS.get(merged.get("pattern"), set())
    return {k: v for k, v in merged.items() if k in keep and v is not None}


def create_payment(db: Session, user: User, category_id: str, body: dict) -> PaymentSchedule:
    category = category_or_404(db, user, category_id)
    not_managed(db, category.id)
    if category.payment_account_id is not None and category.schedules:
        # A card's payment category holds at most one schedule: its plan.
        raise PaymentError(409, "card_plan_exists")
    schedule = PaymentSchedule(user_id=user.id, category_id=category.id)
    _apply(schedule, validate(body))
    db.add(schedule)
    db.flush()
    db.refresh(category)
    refresh_computed_assignments(db, user, category.id)
    return schedule


def update_payment(db: Session, user: User, schedule_id: str, changes: dict) -> PaymentSchedule:
    """Partial update: merged onto the stored row, then re-validated whole.
    Switching pattern drops fields that don't belong to the new one."""
    schedule = schedule_or_404(db, user, schedule_id)
    not_managed(db, schedule.category_id)
    _apply(schedule, validate(merged_fields(fields_of(schedule), changes)))
    db.flush()
    refresh_computed_assignments(db, user, schedule.category_id)
    return schedule


def delete_payment(db: Session, user: User, schedule_id: str) -> str:
    """Delete it and refresh the category; returns the category id."""
    schedule = schedule_or_404(db, user, schedule_id)
    not_managed(db, schedule.category_id)
    category_id = schedule.category_id
    db.delete(schedule)
    db.flush()
    refresh_computed_assignments(db, user, category_id)
    return category_id
