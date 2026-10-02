"""Budget month view, assignment mutations, money moves and suggestion confirmation."""

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
    MoveRequest,
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


@router.post(
    "/{month}/moves",
    response_model=BudgetMonthView,
    responses={
        404: {"description": "Unknown or foreign category (category_not_found)"},
        422: {"description": "same_category | insufficient_available | insufficient_to_be_assigned"},
    },
)
def move_money(
    payload: MoveRequest,
    month: str = MONTH,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BudgetMonthView:
    """Move assigned money between categories (or out of To Be Assigned).

    Two assignment edits in one transaction; bounded by the source's
    available, so a source assignment may go negative when the money comes
    from its rollover (budget-rules design D6).
    """
    if payload.from_category_id == payload.to_category_id:
        raise HTTPException(status_code=422, detail={"code": "same_category"})

    bm = budget_view.materialize_month(db, user, month)
    assignments = {a.category_id: a for a in bm.assignments}
    target = assignments.get(payload.to_category_id)
    source = assignments.get(payload.from_category_id) if payload.from_category_id else None
    if target is None or (payload.from_category_id and source is None):
        raise HTTPException(status_code=404, detail={"code": "category_not_found"})

    view = budget_view.build_view(db, user, month)
    if source is not None:
        available = next(
            c.available_cents
            for g in view.groups
            for c in g.categories
            if c.id == payload.from_category_id
        )
        if payload.amount_cents > available:
            raise HTTPException(
                status_code=422,
                detail={"code": "insufficient_available", "available_cents": available},
            )
        source.assigned_cents -= payload.amount_cents
        source.suggestion_state = "edited"
    elif payload.amount_cents > max(0, view.to_be_assigned_cents):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "insufficient_to_be_assigned",
                "available_cents": max(0, view.to_be_assigned_cents),
            },
        )

    target.assigned_cents += payload.amount_cents
    target.suggestion_state = "edited"
    db.flush()
    return budget_view.build_view(db, user, month)


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
