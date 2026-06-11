"""Budget month derivation — the single seam for all computed values.

available = assigned + rollover − spent
to_be_assigned = income − Σ assigned
rollover(M) = category's available at end of M−1 (recursive over existing
months; zero when no previous month exists). Nothing here is persisted.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import BudgetAssignment, BudgetMonth, Category, CategoryGroup, Transaction, User
from ..schemas import (
    BudgetCategoryView,
    BudgetGroupView,
    BudgetMonthView,
)


def prev_month(month: str) -> str:
    year, mon = (int(p) for p in month.split("-"))
    return f"{year - 1}-12" if mon == 1 else f"{year}-{mon - 1:02d}"


def month_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(p) for p in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


def get_budget_month(db: Session, user: User, month: str) -> BudgetMonth | None:
    return db.scalar(
        select(BudgetMonth).where(BudgetMonth.user_id == user.id, BudgetMonth.month == month)
    )


def materialize_month(db: Session, user: User, month: str) -> BudgetMonth:
    """Lazily create the month; drafts copy the previous month's assignments."""
    existing = get_budget_month(db, user, month)
    if existing is not None:
        return existing

    bm = BudgetMonth(user_id=user.id, month=month)
    db.add(bm)
    db.flush()

    previous = get_budget_month(db, user, prev_month(month))
    prev_assignments: dict[str, int] = {}
    if previous is not None:
        prev_assignments = {a.category_id: a.assigned_cents for a in previous.assignments}

    categories = db.scalars(
        select(Category).where(Category.user_id == user.id, Category.archived.is_(False))
    )
    for category in categories:
        prev_amount = prev_assignments.get(category.id)
        if previous is not None and prev_amount is not None:
            db.add(
                BudgetAssignment(
                    budget_month_id=bm.id,
                    category_id=category.id,
                    assigned_cents=prev_amount,
                    suggestion_cents=prev_amount,
                    suggestion_state="draft",
                )
            )
        else:
            # First month (or new category): zero, no draft.
            db.add(
                BudgetAssignment(
                    budget_month_id=bm.id,
                    category_id=category.id,
                    assigned_cents=0,
                    suggestion_cents=None,
                    suggestion_state="confirmed",
                )
            )
    db.flush()
    return bm


def spent_by_category(db: Session, user: User, month: str) -> dict[str, int]:
    """Spent = |Σ negative confirmed transactions| per category."""
    start, end = month_bounds(month)
    rows = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount_cents))
        .where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.amount_cents < 0,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .group_by(Transaction.category_id)
    ).all()
    return {category_id: -total for category_id, total in rows if category_id}


def income_cents(db: Session, user: User, month: str) -> int:
    start, end = month_bounds(month)
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.amount_cents > 0,
            Transaction.date >= start,
            Transaction.date < end,
        )
    )
    return int(total or 0)


def rollover_by_category(db: Session, user: User, month: str) -> dict[str, int]:
    """Available chain at end of the previous month; {} when none exists.

    Bounded recursion: walks only months that were actually materialized.
    """
    previous = get_budget_month(db, user, prev_month(month))
    if previous is None:
        return {}
    prev_rollover = rollover_by_category(db, user, previous.month)
    prev_spent = spent_by_category(db, user, previous.month)
    result: dict[str, int] = {}
    for a in previous.assignments:
        result[a.category_id] = (
            a.assigned_cents + prev_rollover.get(a.category_id, 0) - prev_spent.get(a.category_id, 0)
        )
    return result


def quickfill_by_category(
    db: Session, user: User, month: str
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Quick-fill sources: (last_assigned, last_spent, avg_3m) per category.

    All empty when no previous materialized month exists. avg_3m averages
    confirmed spending over up to three previous existing months, rounded to
    whole euros in cents.
    """
    previous = get_budget_month(db, user, prev_month(month))
    if previous is None:
        return {}, {}, {}

    last_assigned = {a.category_id: a.assigned_cents for a in previous.assignments}
    last_spent_raw = spent_by_category(db, user, previous.month)
    last_spent = {cid: last_spent_raw.get(cid, 0) for cid in last_assigned}

    spent_months: list[dict[str, int]] = []
    cursor = previous
    while cursor is not None and len(spent_months) < 3:
        spent_months.append(spent_by_category(db, user, cursor.month))
        cursor = get_budget_month(db, user, prev_month(cursor.month))

    avg_3m: dict[str, int] = {}
    for cid in last_assigned:
        total = sum(m.get(cid, 0) for m in spent_months)
        avg_3m[cid] = round(total / len(spent_months) / 100) * 100

    return last_assigned, last_spent, avg_3m


def build_view(db: Session, user: User, month: str) -> BudgetMonthView:
    bm = materialize_month(db, user, month)
    spent = spent_by_category(db, user, month)
    rollover = rollover_by_category(db, user, month)
    last_assigned, last_spent, avg_3m = quickfill_by_category(db, user, month)
    assignments = {a.category_id: a for a in bm.assignments}

    groups = db.scalars(
        select(CategoryGroup)
        .where(CategoryGroup.user_id == user.id)
        .order_by(CategoryGroup.sort_order)
    )

    group_views: list[BudgetGroupView] = []
    total_assigned = 0
    for group in groups:
        cat_views: list[BudgetCategoryView] = []
        for category in group.categories:
            assignment = assignments.get(category.id)
            assigned = assignment.assigned_cents if assignment else 0
            cat_spent = spent.get(category.id, 0)
            cat_rollover = rollover.get(category.id, 0)
            # Archived categories stay visible in months where they have
            # activity, so historical months render unchanged (manage-
            # categories design D1); only inactive ones drop out.
            if category.archived and not (assigned or cat_spent or cat_rollover):
                continue
            total_assigned += assigned
            cat_views.append(
                BudgetCategoryView(
                    id=category.id,
                    name=category.name,
                    icon=category.icon,
                    assigned_cents=assigned,
                    spent_cents=cat_spent,
                    rollover_cents=cat_rollover,
                    available_cents=assigned + cat_rollover - cat_spent,
                    suggestion_cents=assignment.suggestion_cents if assignment else None,
                    suggestion_state=(
                        assignment.suggestion_state if assignment else "confirmed"
                    ),  # type: ignore[arg-type]
                    last_month_assigned_cents=last_assigned.get(category.id),
                    avg_3m_cents=avg_3m.get(category.id),
                    last_month_spent_cents=last_spent.get(category.id),
                )
            )
        group_views.append(
            BudgetGroupView(
                id=group.id, name=group.name, sort_order=group.sort_order, categories=cat_views
            )
        )

    income = income_cents(db, user, month)
    return BudgetMonthView(
        month=month,
        income_cents=income,
        to_be_assigned_cents=income - total_assigned,
        groups=group_views,
    )
