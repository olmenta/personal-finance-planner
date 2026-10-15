"""Validation shared by every money move: the budget's move endpoint and the
coach's funded raise (redesign-safety-baseline D4). Validate first, mutate
after, inside the request transaction."""

from ..schemas import BudgetCategoryView, BudgetMonthView


class MoveError(Exception):
    def __init__(self, status: int, code: str, extra: dict | None = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.extra = extra or {}


def find_category(view: BudgetMonthView, category_id: str) -> BudgetCategoryView | None:
    return next((c for g in view.groups for c in g.categories if c.id == category_id), None)


def validate_source(
    view: BudgetMonthView, target_id: str, source_id: str, amount_cents: int
) -> BudgetCategoryView:
    """The source differs from the target, exists in the month, and its
    available covers the amount."""
    if source_id == target_id:
        raise MoveError(422, "same_category")
    source = find_category(view, source_id)
    if source is None:
        raise MoveError(404, "category_not_found")
    if amount_cents > source.available_cents:
        raise MoveError(
            422, "insufficient_available", {"available_cents": source.available_cents}
        )
    return source


def set_assignment(db, user, month: str, category_id: str, amount_cents: int):
    """The assignment PUT rule, shared by the form and the coach: categories
    with payments are computed, never typed (409 assignment_from_payments)."""
    from . import budget_view
    from .schedules import schedules_by_category

    bm = budget_view.materialize_month(db, user, month)
    assignment = budget_view.ensure_assignment(db, user, bm, category_id)
    if assignment is None:
        raise MoveError(404, "category_not_found")
    if schedules_by_category(db, user).get(category_id):
        raise MoveError(409, "assignment_from_payments")
    assignment.assigned_cents = amount_cents
    assignment.suggestion_state = "edited"
    db.flush()
    return assignment


def apply_move(db, user, month: str, from_id: str | None, to_id: str, amount_cents: int) -> None:
    """Move assigned money between categories, or out of To Be Assigned
    (budget-rules design D6). Validates first, then edits both assignments."""
    from . import budget_view

    if from_id == to_id:
        raise MoveError(422, "same_category")
    bm = budget_view.materialize_month(db, user, month)
    target = budget_view.ensure_assignment(db, user, bm, to_id)
    source = budget_view.ensure_assignment(db, user, bm, from_id) if from_id else None
    if target is None or (from_id and source is None):
        raise MoveError(404, "category_not_found")
    view = budget_view.build_view(db, user, month)
    if source is not None:
        validate_source(view, to_id, from_id, amount_cents)
        source.assigned_cents -= amount_cents
        source.suggestion_state = "edited"
    elif amount_cents > max(0, view.to_be_assigned_cents):
        raise MoveError(422, "insufficient_to_be_assigned",
                        {"available_cents": max(0, view.to_be_assigned_cents)})
    target.assigned_cents += amount_cents
    target.suggestion_state = "edited"
    db.flush()
