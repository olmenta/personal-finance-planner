"""Month summary aggregation for the dashboard.

balance = all-time sum of confirmed transaction amounts (signed cents;
transfer twins cancel out); income = uncategorized positive rows (shared
filter with the budget view — categorized inflows are refunds and net the
expense side instead, transfer twins never count); week
buckets are Monday-based calendar weeks clamped to the month. Aggregation
happens in SQL grouped by date — the date→bucket mapping stays in Python so
the SQL is dialect-portable.
"""

from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..models import Transaction, User
from ..schemas import SummaryView, SummaryWeek
from .budget_view import income_filters, month_bounds


def week_starts(month: str) -> list[date]:
    """First day of each Monday-based week overlapping the month, clamped."""
    start, end = month_bounds(month)
    starts = [start]
    cursor = start + timedelta(days=7 - start.weekday())  # next Monday
    while cursor < end:
        starts.append(cursor)
        cursor += timedelta(days=7)
    return starts


def build_summary(db: Session, user: User, month: str) -> SummaryView:
    start, end = month_bounds(month)

    balance = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
        )
    )

    daily = db.execute(
        select(Transaction.date, func.sum(Transaction.amount_cents))
        .where(
            *income_filters(user),
            Transaction.date >= start,
            Transaction.date < end,
        )
        .group_by(Transaction.date)
    ).all()
    # Expense side: all expenses plus categorized inflows (refunds), which
    # net the day's spending down instead of counting as income. Transfer
    # twins and opening balances (e.g. a card's pre-existing debt) are not
    # spending.
    daily_spent = db.execute(
        select(Transaction.date, func.sum(Transaction.amount_cents))
        .where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.date >= start,
            Transaction.date < end,
            Transaction.transfer_pair_id.is_(None),
            Transaction.source != "opening_balance",
            or_(
                Transaction.amount_cents < 0,
                and_(Transaction.amount_cents > 0, Transaction.category_id.is_not(None)),
            ),
        )
        .group_by(Transaction.date)
    ).all()

    starts = week_starts(month)

    def bucket_index(day: date) -> int:
        for i in range(len(starts) - 1, -1, -1):
            if day >= starts[i]:
                return i
        return 0

    weeks = [SummaryWeek(start=s, spent_cents=0, income_cents=0) for s in starts]
    income_total = 0
    expense_total = 0
    for day, total in daily:
        income_total += total
        weeks[bucket_index(day)].income_cents += total
    for day, total in daily_spent:
        expense_total += -total
        weeks[bucket_index(day)].spent_cents += -total

    return SummaryView(
        month=month,
        balance_cents=int(balance or 0),
        income_cents=income_total,
        expense_cents=expense_total,
        weeks=weeks,
    )
