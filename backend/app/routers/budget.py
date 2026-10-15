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
from ..services.budget_moves import MoveError, apply_move, set_assignment

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
    try:
        assignment = set_assignment(db, user, month, category_id, payload.amount_cents)
    except MoveError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from error

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
    try:
        apply_move(db, user, month, payload.from_category_id, payload.to_category_id,
                   payload.amount_cents)
    except MoveError as error:
        raise HTTPException(
            status_code=error.status, detail={"code": error.code, **error.extra}
        ) from error
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
