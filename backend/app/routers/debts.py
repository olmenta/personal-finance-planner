"""Debts: what's owed, the paydown order and the plan (spec: debts)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import DebtExtraIn, DebtsView
from ..services import debt_ops
from ..services import debts as service

router = APIRouter(tags=["debts"])


def _fail(error: service.DebtError) -> HTTPException:
    return HTTPException(status_code=error.status, detail={"code": error.code})


@router.get("/debts", response_model=DebtsView)
def list_debts(db: Session = Depends(get_db), user: User = Depends(current_user)) -> DebtsView:
    return service.build_debts_view(db, user)


@router.post("/debts", response_model=DebtsView, status_code=201)
def create_debt(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DebtsView:
    try:
        debt_ops.create(db, user, body)
    except service.DebtError as error:
        raise _fail(error) from error
    return service.build_debts_view(db, user)


@router.patch("/debts/{debt_id}", response_model=DebtsView)
def update_debt(
    debt_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DebtsView:
    try:
        debt_ops.update(db, user, debt_id, body)
    except service.DebtError as error:
        raise _fail(error) from error
    return service.build_debts_view(db, user)


@router.delete("/debts/{debt_id}", status_code=204)
def delete_debt(
    debt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    try:
        debt_ops.delete(db, user, debt_id)
    except service.DebtError as error:
        raise _fail(error) from error


@router.put("/debts/extra", response_model=DebtsView)
def put_extra(
    body: DebtExtraIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DebtsView:
    debt_ops.set_extra(db, user, body.extra_monthly_cents)
    return service.build_debts_view(db, user)
