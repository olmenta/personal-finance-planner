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
