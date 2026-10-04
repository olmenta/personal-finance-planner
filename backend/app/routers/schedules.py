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
) -> list[PaymentSchedule]:
    return list(_category_or_404(db, user, category_id).schedules)


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
    category_id = schedule.category_id
    db.delete(schedule)
    db.flush()
    refresh_computed_assignments(db, user, category_id)
