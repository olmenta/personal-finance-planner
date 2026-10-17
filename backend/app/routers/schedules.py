"""Payment schedules CRUD (spec: payment-schedules)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import PaymentSchedule, User
from ..schemas import ScheduleOut
from ..services import payment_ops
from ..services.debts import debt_for_category

router = APIRouter(tags=["schedules"])


def _http(error: payment_ops.PaymentError) -> HTTPException:
    return HTTPException(status_code=error.status, detail={"code": error.code})


def _with_debt(db: Session, category_id: str, schedules: list[PaymentSchedule]) -> list[ScheduleOut]:
    debt = debt_for_category(db, category_id)
    return [
        ScheduleOut.model_validate(s).model_copy(update={"debt_id": debt.id if debt else None})
        for s in schedules
    ]


@router.get("/categories/{category_id}/schedules", response_model=list[ScheduleOut])
def list_schedules(
    category_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ScheduleOut]:
    try:
        category = payment_ops.category_or_404(db, user, category_id)
    except payment_ops.PaymentError as error:
        raise _http(error) from error
    return _with_debt(db, category_id, list(category.schedules))


@router.post(
    "/categories/{category_id}/schedules", response_model=ScheduleOut, status_code=201
)
def create_schedule(
    category_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PaymentSchedule:
    try:
        return payment_ops.create_payment(db, user, category_id, body)
    except payment_ops.PaymentError as error:
        raise _http(error) from error


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PaymentSchedule:
    try:
        return payment_ops.update_payment(db, user, schedule_id, body)
    except payment_ops.PaymentError as error:
        raise _http(error) from error


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    try:
        payment_ops.delete_payment(db, user, schedule_id)
    except payment_ops.PaymentError as error:
        raise _http(error) from error
