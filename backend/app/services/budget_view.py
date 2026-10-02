"""Budget month derivation — the single seam for all computed values.

available(c, M)      = assigned + rollover − spent
rollover(c, M)       = max(0, available(c, M−1))      overspending resets…
overspent(M)         = Σ max(0, −available(c, M))
to_be_assigned(M)    = TBA(M−1) + unbudgeted(M) − Σ assigned(M) − overspent(M−1)
                                                     …and is paid from TBA
TBA(start−1)         = signed sum of confirmed activity before the budget start

One forward pass over calendar months from the first materialized month;
unopened months count as zero assignments and are never materialized here.
Invariant: TBA(M) + Σ available(M) = Σ confirmed activity up to the end of M.
Nothing here is persisted.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import BudgetAssignment, BudgetMonth, Category, CategoryGroup, Transaction, User
from ..schemas import (
    BudgetCategoryView,
    BudgetGroupView,
    BudgetMonthView,
    CoverSuggestion,
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
    """Spent = negated net of signed confirmed activity per category.

    Categorized inflows are refunds: they restore the category's available
    instead of counting as income (spec: budget-api, refund scenario).
    """
    start, end = month_bounds(month)
    rows = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount_cents))
        .where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.date >= start,
            Transaction.date < end,
        )
        .group_by(Transaction.category_id)
    ).all()
    return {category_id: -total for category_id, total in rows if category_id}


def income_filters(user: User) -> tuple:
    """What counts as income: confirmed, positive, and uncategorized —
    a categorized inflow is a refund (category activity), not income.
    Shared with the summary so dashboard and budget can never disagree."""
    return (
        Transaction.user_id == user.id,
        Transaction.status == "confirmed",
        Transaction.amount_cents > 0,
        Transaction.category_id.is_(None),
    )


def income_cents(db: Session, user: User, month: str) -> int:
    start, end = month_bounds(month)
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            *income_filters(user),
            Transaction.date >= start,
            Transaction.date < end,
        )
    )
    return int(total or 0)


def _month_index(month: str) -> int:
    year, mon = (int(p) for p in month.split("-"))
    return year * 12 + mon - 1


def _month_from_index(index: int) -> str:
    return f"{index // 12}-{index % 12 + 1:02d}"


@dataclass
class MonthChain:
    """Where month M starts: per-category rollover and the TBA carry-in."""

    rollover: dict[str, int]
    reset: dict[str, int]  # per-category overspending of M−1 that didn't carry
    carried_in: int  # TBA(M−1)
    overspent_deducted: int  # overspent(M−1)
    unbudgeted: int  # signed uncategorized activity in M


def month_chain(db: Session, user: User, month: str) -> MonthChain:
    """Forward pass from the budget start to `month` (design D1–D5).

    Three grouped queries over the whole range, then a pass in Python.
    """
    first = db.scalar(select(func.min(BudgetMonth.month)).where(BudgetMonth.user_id == user.id))
    start = first if first is not None and first < month else month
    range_start, _ = month_bounds(start)
    _, range_end = month_bounds(month)

    month_col = func.to_char(Transaction.date, "YYYY-MM")
    in_range = (
        Transaction.user_id == user.id,
        Transaction.status == "confirmed",
        Transaction.date >= range_start,
        Transaction.date < range_end,
    )
    spent: dict[str, dict[str, int]] = {}
    for m, category_id, total in db.execute(
        select(month_col, Transaction.category_id, func.sum(Transaction.amount_cents))
        .where(*in_range, Transaction.category_id.is_not(None))
        .group_by(month_col, Transaction.category_id)
    ):
        spent.setdefault(m, {})[category_id] = -int(total)
    unbudgeted = {
        m: int(total)
        for m, total in db.execute(
            select(month_col, func.sum(Transaction.amount_cents))
            .where(*in_range, Transaction.category_id.is_(None))
            .group_by(month_col)
        )
    }
    assigned: dict[str, dict[str, int]] = {}
    for m, category_id, cents in db.execute(
        select(BudgetMonth.month, BudgetAssignment.category_id, BudgetAssignment.assigned_cents)
        .join(BudgetAssignment, BudgetAssignment.budget_month_id == BudgetMonth.id)
        .where(BudgetMonth.user_id == user.id, BudgetMonth.month >= start, BudgetMonth.month < month)
    ):
        assigned.setdefault(m, {})[category_id] = cents
    pre_start = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.date < range_start,
        )
    )

    rollover: dict[str, int] = {}
    reset: dict[str, int] = {}
    tba = int(pre_start or 0)
    overspent_prev = 0
    for index in range(_month_index(start), _month_index(month)):
        m = _month_from_index(index)
        m_assigned = assigned.get(m, {})
        m_spent = spent.get(m, {})
        tba += unbudgeted.get(m, 0) - sum(m_assigned.values()) - overspent_prev
        overspent_prev = 0
        reset = {}
        next_rollover: dict[str, int] = {}
        for category_id in rollover.keys() | m_assigned.keys() | m_spent.keys():
            available = (
                m_assigned.get(category_id, 0)
                + rollover.get(category_id, 0)
                - m_spent.get(category_id, 0)
            )
            if available < 0:
                overspent_prev += -available
                reset[category_id] = -available
            next_rollover[category_id] = max(0, available)
        rollover = next_rollover

    return MonthChain(
        rollover=rollover,
        reset=reset,
        carried_in=tba,
        overspent_deducted=overspent_prev,
        unbudgeted=unbudgeted.get(month, 0),
    )


def cover_suggestions(
    available: dict[str, int], to_be_assigned: int
) -> dict[str, CoverSuggestion]:
    """Greedy cover sources, largest overspending first (design D7).

    Positive TBA first, then the non-overspent category with the most
    available; sources are consumed so two suggestions never share euros.
    """
    overspent = sorted(
        ((cid, -a) for cid, a in available.items() if a < 0), key=lambda item: -item[1]
    )
    tba_left = max(0, to_be_assigned)
    donors = {cid: a for cid, a in available.items() if a > 0}
    result: dict[str, CoverSuggestion] = {}
    for category_id, amount in overspent:
        if tba_left > 0:
            take = min(amount, tba_left)
            tba_left -= take
            result[category_id] = CoverSuggestion(source_category_id=None, amount_cents=take)
            continue
        donor = max(donors, key=lambda cid: donors[cid], default=None)
        if donor is None or donors[donor] <= 0:
            continue
        take = min(amount, donors[donor])
        donors[donor] -= take
        result[category_id] = CoverSuggestion(source_category_id=donor, amount_cents=take)
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
    chain = month_chain(db, user, month)
    rollover = chain.rollover
    last_assigned, last_spent, avg_3m = quickfill_by_category(db, user, month)
    assignments = {a.category_id: a for a in bm.assignments}

    groups = db.scalars(
        select(CategoryGroup)
        .where(CategoryGroup.user_id == user.id)
        .order_by(CategoryGroup.sort_order)
    )

    total_assigned = sum(a.assigned_cents for a in bm.assignments)
    to_be_assigned = (
        chain.carried_in + chain.unbudgeted - total_assigned - chain.overspent_deducted
    )

    rows: list[tuple[CategoryGroup, list[BudgetCategoryView]]] = []
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
            available = assigned + cat_rollover - cat_spent
            cat_views.append(
                BudgetCategoryView(
                    id=category.id,
                    name=category.name,
                    icon=category.icon,
                    assigned_cents=assigned,
                    spent_cents=cat_spent,
                    rollover_cents=cat_rollover,
                    available_cents=available,
                    overspent_cents=max(0, -available),
                    rollover_reset_cents=chain.reset.get(category.id, 0),
                    suggestion_cents=assignment.suggestion_cents if assignment else None,
                    suggestion_state=(
                        assignment.suggestion_state if assignment else "confirmed"
                    ),  # type: ignore[arg-type]
                    last_month_assigned_cents=last_assigned.get(category.id),
                    avg_3m_cents=avg_3m.get(category.id),
                    last_month_spent_cents=last_spent.get(category.id),
                )
            )
        rows.append((group, cat_views))

    suggestions = cover_suggestions(
        {c.id: c.available_cents for _, cats in rows for c in cats}, to_be_assigned
    )
    group_views = [
        BudgetGroupView(
            id=group.id,
            name=group.name,
            sort_order=group.sort_order,
            categories=[
                c.model_copy(update={"cover_suggestion": suggestions.get(c.id)}) for c in cats
            ],
        )
        for group, cats in rows
    ]

    return BudgetMonthView(
        month=month,
        income_cents=income_cents(db, user, month),
        to_be_assigned_cents=to_be_assigned,
        carried_in_cents=chain.carried_in,
        overspent_deducted_cents=chain.overspent_deducted,
        groups=group_views,
    )
