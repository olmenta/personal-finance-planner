"""Payment schedules CRUD (spec: payment-schedules)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Category, PaymentSchedule, User
from ..schemas import SCHEDULE_FIELDS, ScheduleIn, ScheduleOut
from ..services.budget_view import refresh_computed_assignments
from ..services.debts import debt_for_category

router = APIRouter(tags=["schedules"])

_validator: TypeAdapter = TypeAdapter(ScheduleIn)


def _validate(body: dict):
    try:
        return _validator.validate_python(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_schedule"}) from exc


def _apply(schedule: PaymentSchedule, valid) -> None:
    data = valid.model_dump()
    for field in SCHEDULE_FIELDS:
        setattr(schedule, field, data.get(field))
    if schedule.estimated is None:
        schedule.estimated = False


def _category_or_404(db: Session, user: User, category_id: str) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail={"code": "category_not_found"})
    return category


def _not_managed(db: Session, category_id: str) -> None:
    """Debt schedules are written only through the debts API (debts design D4)."""
    if debt_for_category(db, category_id) is not None:
        raise HTTPException(status_code=409, detail={"code": "managed_by_debt"})


def _with_debt(db: Session, category_id: str, schedules: list[PaymentSchedule]) -> list[ScheduleOut]:
    debt = debt_for_category(db, category_id)
    return [
        ScheduleOut.model_validate(s).model_copy(update={"debt_id": debt.id if debt else None})
        for s in schedules
    ]


def _schedule_or_404(db: Session, user: User, schedule_id: str) -> PaymentSchedule:
    schedule = db.scalar(
        select(PaymentSchedule).where(
            PaymentSchedule.id == schedule_id, PaymentSchedule.user_id == user.id
        )
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail={"code": "schedule_not_found"})
    return schedule


@router.get("/categories/{category_id}/schedules", response_model=list[ScheduleOut])
def list_schedules(
    category_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ScheduleOut]:
    return _with_debt(db, category_id, list(_category_or_404(db, user, category_id).schedules))


@router.post(
    "/categories/{category_id}/schedules", response_model=ScheduleOut, status_code=201
)
def create_schedule(
    category_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PaymentSchedule:
    category = _category_or_404(db, user, category_id)
    _not_managed(db, category.id)
    if category.payment_account_id is not None and category.schedules:
        # A card's payment category holds at most one schedule: its plan.
        raise HTTPException(status_code=409, detail={"code": "card_plan_exists"})
    schedule = PaymentSchedule(user_id=user.id, category_id=category.id)
    _apply(schedule, _validate(body))
    db.add(schedule)
    db.flush()
    db.refresh(category)
    refresh_computed_assignments(db, user, category.id)
    return schedule


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PaymentSchedule:
    """Partial update: merged onto the stored row, then re-validated whole.
    Switching pattern drops fields that don't belong to the new one."""
    schedule = _schedule_or_404(db, user, schedule_id)
    _not_managed(db, schedule.category_id)
    merged = {f: getattr(schedule, f) for f in SCHEDULE_FIELDS} | body
    pattern_fields = {
        "monthly": {"count", "start_month"},
        "some_months": {"months"},
        "annual": {"month"},
        "every_n": {"every_n", "start_month"},
        "once": {"once_month"},
        "no_date": set(),
    }.get(merged.get("pattern"), set())
    common = {"name", "amount_cents", "pattern", "day", "estimated"}
    merged = {k: v for k, v in merged.items() if k in common | pattern_fields and v is not None}
    _apply(schedule, _validate(merged))
    db.flush()
    refresh_computed_assignments(db, user, schedule.category_id)
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    schedule = _schedule_or_404(db, user, schedule_id)
    _not_managed(db, schedule.category_id)
    category_id = schedule.category_id
    db.delete(schedule)
    db.flush()
    refresh_computed_assignments(db, user, category_id)
