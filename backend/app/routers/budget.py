"""Budget month view, assignment mutations and suggestion confirmation."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import BudgetAssignment, User
from ..schemas import (
    AssignRequest,
    AssignResponse,
    BudgetMonthView,
    ConfirmSuggestionsRequest,
)
from ..services import budget_view

router = APIRouter(prefix="/budget", tags=["budget"])

MONTH = Path(pattern=r"^\d{4}-\d{2}$")


@router.get("/{month}", response_model=BudgetMonthView)
def get_month(
    month: str = MONTH,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BudgetMonthView:
    return budget_view.build_view(db, user, month)


@router.put("/{month}/assignments/{category_id}", response_model=AssignResponse)
def assign(
    payload: AssignRequest,
    month: str = MONTH,
    category_id: str = Path(),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AssignResponse:
    bm = budget_view.materialize_month(db, user, month)
    assignment = db.scalar(
        select(BudgetAssignment).where(
            BudgetAssignment.budget_month_id == bm.id,
            BudgetAssignment.category_id == category_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail={"code": "category_not_found"})

    assignment.assigned_cents = payload.amount_cents
    assignment.suggestion_state = "edited"
    db.flush()

    view = budget_view.build_view(db, user, month)
    return AssignResponse(
        category_id=category_id,
        assigned_cents=assignment.assigned_cents,
        suggestion_state=assignment.suggestion_state,
        to_be_assigned_cents=view.to_be_assigned_cents,
    )


@router.post("/{month}/confirm-suggestions", response_model=BudgetMonthView)
def confirm_suggestions(
    payload: ConfirmSuggestionsRequest,
    month: str = MONTH,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BudgetMonthView:
    bm = budget_view.materialize_month(db, user, month)
    assignments = db.scalars(
        select(BudgetAssignment).where(
            BudgetAssignment.budget_month_id == bm.id,
            BudgetAssignment.category_id.in_(payload.category_ids),
        )
    )
    for assignment in assignments:
        # Drafts confirm in place; edited rows are never overwritten.
        if assignment.suggestion_state == "draft":
            assignment.suggestion_state = "confirmed"
    db.flush()
    return budget_view.build_view(db, user, month)
