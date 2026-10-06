"""Debts: what's owed, the paydown order and the plan (spec: debts)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Debt, User
from ..schemas import DebtExtraIn, DebtIn, DebtsView, DebtUpdate
from ..services import debts as service

router = APIRouter(tags=["debts"])

_create: TypeAdapter = TypeAdapter(DebtIn)


def _fail(error: service.DebtError) -> HTTPException:
    return HTTPException(status_code=error.status, detail={"code": error.code})


def _debt_or_404(db: Session, user: User, debt_id: str) -> Debt:
    debt = db.scalar(select(Debt).where(Debt.id == debt_id, Debt.user_id == user.id))
    if debt is None:
        raise HTTPException(status_code=404, detail={"code": "debt_not_found"})
    return debt


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
        valid = _create.validate_python(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_debt"}) from exc
    try:
        service.create_debt(db, user, valid)
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
    debt = _debt_or_404(db, user, debt_id)
    try:
        valid = DebtUpdate.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_debt"}) from exc
    try:
        service.update_debt(db, user, debt, valid)
    except service.DebtError as error:
        raise _fail(error) from error
    return service.build_debts_view(db, user)


@router.delete("/debts/{debt_id}", status_code=204)
def delete_debt(
    debt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    service.delete_debt(db, user, _debt_or_404(db, user, debt_id))


@router.put("/debts/extra", response_model=DebtsView)
def put_extra(
    body: DebtExtraIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DebtsView:
    service.settings(db, user).extra_monthly_cents = body.extra_monthly_cents
    db.flush()
    return service.build_debts_view(db, user)
