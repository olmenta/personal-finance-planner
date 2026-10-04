"""Month overview — "Este mes" (category-targets design D5).

Partitions Σ available exactly into covered payments, left to spend and
saved (minus overspent), so with To Be Assigned it adds up to the money in
the accounts: accounts = covered + left + saved + TBA − overspent.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clock import today_madrid
from ..models import PaymentSchedule, Transaction, User
from ..schemas import (
    BudgetCategoryView,
    BudgetMonthView,
    OverviewAmountItem,
    OverviewAmountSection,
    OverviewPaidItem,
    OverviewPaidSection,
    OverviewPending,
    OverviewView,
)
from . import schedules as sched
from .budget_view import build_view, month_bounds

@dataclass
class Occurrence:
    schedule: PaymentSchedule
    allocated: int = 0
    paid: bool = False

    @property
    def pending(self) -> int:
        return 0 if self.paid else self.schedule.amount_cents - self.allocated


@dataclass
class CategoryMatch:
    occurrences: list[Occurrence] = field(default_factory=list)
    leftover_spent: int = 0  # spending not explained by this month's payments

    @property
    def pending(self) -> int:
        return sum(o.pending for o in self.occurrences)


def match_payments(
    schedules: list[PaymentSchedule], month: str, spent: int
) -> CategoryMatch:
    """Allocate the category's spending to its occurrences in day order. An
    occurrence is paid when covered, or — if estimated — once any spending
    lands on it (the bill arrived; the difference is ordinary spending)."""
    due = sorted(
        (s for s in schedules if sched.occurs(s, month)), key=lambda s: (s.day or 1, s.created_at)
    )
    remaining = max(0, spent)
    match = CategoryMatch()
    for schedule in due:
        take = min(remaining, schedule.amount_cents)
        remaining -= take
        paid = take >= schedule.amount_cents or (schedule.estimated and take > 0)
        match.occurrences.append(Occurrence(schedule=schedule, allocated=take, paid=paid))
    match.leftover_spent = remaining
    return match


def _categories(view: BudgetMonthView) -> list[tuple[str, BudgetCategoryView]]:
    return [(g.name, c) for g in view.groups for c in g.categories]


def build_overview(
    db: Session, user: User, month: str, today: date | None = None
) -> OverviewView:
    view = build_view(db, user, month)
    by_category = sched.schedules_by_category(db, user)

    paid_items: list[OverviewPaidItem] = []
    to_pay: list[OverviewPending] = []
    left_items: list[OverviewAmountItem] = []
    saved_items: list[OverviewAmountItem] = []
    left = saved = overspent = 0

    for group_name, c in _categories(view):
        a = c.available_cents
        schedules = by_category.get(c.id, [])
        match = match_payments(schedules, month, c.spent_cents)
        for occ in match.occurrences:
            if occ.paid:
                paid_items.append(
                    OverviewPaidItem(
                        category_id=c.id,
                        category_name=c.name,
                        name=occ.schedule.name,
                        day=occ.schedule.day,
                        amount_cents=occ.allocated,
                    )
                )
        if match.leftover_spent > 0:
            paid_items.append(
                OverviewPaidItem(
                    category_id=c.id, category_name=c.name, name=None, day=None,
                    amount_cents=match.leftover_spent,
                )
            )

        if c.kind == "scheduled":
            pending = match.pending
            reserve = a
            for occ in match.occurrences:
                if occ.paid:
                    continue
                covered = max(0, min(occ.pending, reserve))
                to_pay.append(
                    OverviewPending(
                        category_id=c.id,
                        category_name=c.name,
                        schedule_id=occ.schedule.id,
                        name=occ.schedule.name,
                        day=occ.schedule.day,
                        amount_cents=occ.pending,
                        covered_cents=covered,
                        short_cents=occ.pending - covered,
                        estimated=occ.schedule.estimated,
                    )
                )
                reserve -= occ.pending
            if a < 0:
                overspent += -a
            elif a > pending:
                saved += a - pending
                saved_items.append(
                    OverviewAmountItem(
                        category_id=c.id, name=c.name, group=group_name, amount_cents=a - pending
                    )
                )
        elif c.kind == "savings":
            if a < 0:
                overspent += -a
            else:
                saved += a
                saved_items.append(
                    OverviewAmountItem(category_id=c.id, name=c.name, group=group_name, amount_cents=a)
                )
        else:  # flexible
            if a < 0:
                overspent += -a
            else:
                left += a
            left_items.append(
                OverviewAmountItem(
                    category_id=c.id, name=c.name, group=group_name, amount_cents=a,
                    spent_cents=c.spent_cents,
                )
            )

    _, end = month_bounds(month)
    accounts = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.date < end,
        )
    )
    paid_items.sort(key=lambda p: (p.day is None, p.day or 0))
    to_pay.sort(key=lambda p: (p.day or 1))
    return OverviewView(
        month=month,
        today=today or today_madrid(),
        paid=OverviewPaidSection(
            total_cents=sum(p.amount_cents for p in paid_items), items=paid_items
        ),
        to_pay=to_pay,
        to_pay_total_cents=sum(p.amount_cents for p in to_pay),
        covered_cents=sum(p.covered_cents for p in to_pay),
        left_to_spend=OverviewAmountSection(total_cents=left, items=left_items),
        saved=OverviewAmountSection(total_cents=saved, items=saved_items),
        overspent_cents=overspent,
        to_be_assigned_cents=view.to_be_assigned_cents,
        accounts_cents=int(accounts or 0),
    )
