"""Income schedules CRUD and the month's expected-versus-received view
(spec: income-schedules)."""

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import IncomeSchedule, User
from ..schemas import (
    SCHEDULE_FIELDS,
    IncomeScheduleIn,
    IncomeScheduleOut,
    MonthIncomeView,
)
from ..services import income as income_service

router = APIRouter(tags=["income"])

_validator: TypeAdapter = TypeAdapter(IncomeScheduleIn)

_PATTERN_FIELDS = {
    "monthly": {"count", "start_month"},
    "some_months": {"months"},
    "annual": {"month"},
    "every_n": {"every_n", "start_month"},
    "once": {"once_month"},
}
_COMMON = {"name", "amount_cents", "pattern", "day", "estimated", "payer"}


def _validate(body: dict):
    try:
        return _validator.validate_python(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_schedule"}) from exc


def _out(schedule: IncomeSchedule) -> IncomeScheduleOut:
    return IncomeScheduleOut.model_validate(
        {
            **{f: getattr(schedule, f) for f in SCHEDULE_FIELDS},
            "id": schedule.id,
            "payee_id": schedule.payee_id,
            "payer": schedule.payer,
            "yearly_cents": income_service.yearly_cents(schedule),
        }
    )


def _schedule_or_404(db: Session, user: User, schedule_id: str) -> IncomeSchedule:
    schedule = db.scalar(
        select(IncomeSchedule).where(
            IncomeSchedule.id == schedule_id, IncomeSchedule.user_id == user.id
        )
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail={"code": "income_schedule_not_found"})
    return schedule


@router.get("/income-schedules", response_model=list[IncomeScheduleOut])
def list_income_schedules(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[IncomeScheduleOut]:
    schedules = sorted(
        income_service.user_schedules(db, user),
        key=lambda s: (s.day is None, s.day or 0, s.created_at),
    )
    return [_out(s) for s in schedules]


@router.post("/income-schedules", response_model=IncomeScheduleOut, status_code=201)
def create_income_schedule(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> IncomeScheduleOut:
    valid = _validate(body)
    schedule = IncomeSchedule(user_id=user.id)
    income_service.apply_schedule(db, user.id, schedule, valid)
    db.add(schedule)
    db.flush()
    return _out(schedule)


@router.patch("/income-schedules/{schedule_id}", response_model=IncomeScheduleOut)
def update_income_schedule(
    schedule_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> IncomeScheduleOut:
    """Partial update: merged onto the stored row, then re-validated whole.
    Switching pattern drops fields that don't belong to the new one; an empty
    `payer` clears it."""
    schedule = _schedule_or_404(db, user, schedule_id)
    stored = {f: getattr(schedule, f) for f in SCHEDULE_FIELDS} | {"payer": schedule.payer}
    merged = stored | body
    if "payer" in body and body["payer"] is None:
        merged["payer"] = ""
    allowed = _COMMON | _PATTERN_FIELDS.get(merged.get("pattern"), set())
    merged = {k: v for k, v in merged.items() if k in allowed and v is not None}
    income_service.apply_schedule(db, user.id, schedule, _validate(merged))
    db.flush()
    return _out(schedule)


@router.delete("/income-schedules/{schedule_id}", status_code=204)
def delete_income_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    db.delete(_schedule_or_404(db, user, schedule_id))
    db.flush()


@router.get("/income/{month}", response_model=MonthIncomeView)
def month_income(
    month: str = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MonthIncomeView:
    return income_service.month_income(db, user, month)
