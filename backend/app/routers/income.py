"""Income schedules CRUD and the month's expected-versus-received view
(spec: income-schedules)."""

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import IncomeSchedule, User
from ..schemas import (
    SCHEDULE_FIELDS,
    IncomeLinkIn,
    IncomeScheduleOut,
    MonthIncomeView,
)
from ..services import income as income_service
from ..services import income_ops

router = APIRouter(tags=["income"])


def _http(error: income_ops.IncomeError) -> HTTPException:
    return HTTPException(status_code=error.status, detail={"code": error.code})


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
    try:
        return _out(income_ops.create_income(db, user, body))
    except income_ops.IncomeError as error:
        raise _http(error) from error


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
    try:
        return _out(income_ops.update_income(db, user, schedule_id, body))
    except income_ops.IncomeError as error:
        raise _http(error) from error


@router.delete("/income-schedules/{schedule_id}", status_code=204)
def delete_income_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    try:
        income_ops.delete_income(db, user, schedule_id)
    except income_ops.IncomeError as error:
        raise _http(error) from error


@router.post("/income/link", response_model=MonthIncomeView)
def link_income(
    body: IncomeLinkIn = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MonthIncomeView:
    """"This is…": link an unplanned inflow to an expected income, in one step."""
    try:
        income_ops.link_income(db, user, body.transaction_id, body.schedule_id)
        txn = income_ops.inflow_or_404(db, user, body.transaction_id)
    except income_ops.IncomeError as error:
        raise _http(error) from error
    return income_service.month_income(db, user, txn.date.strftime("%Y-%m"))


@router.get("/income/{month}", response_model=MonthIncomeView)
def month_income(
    month: str = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MonthIncomeView:
    return income_service.month_income(db, user, month)
