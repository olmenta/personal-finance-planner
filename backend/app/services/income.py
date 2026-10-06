"""Expected income versus received (spec: income-schedules, design D4).

Income schedules say when money is expected; confirmed income inflows (the
`income_cents` rule) say what arrived. Matching runs on every read and is
never persisted:

1. By payee — whole inflows go to the earliest unreceived occurrence of that
   payee; an inflow reaching 90 % of the running sum also covers the next one
   (salary and extra pay arriving together).
2. By amount — leftover inflows go to the closest unreceived occurrence of a
   schedule without payee within 10 % (25 % when estimated).

Nothing here touches To Be Assigned: only real transactions fund the budget.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import IncomeSchedule, Transaction, User
from ..schemas import SCHEDULE_FIELDS, IncomeOccurrence, MonthIncomeView, UnplannedIncome
from . import schedules as sched
from .budget_view import income_filters, month_bounds
from .payees import resolve_payee

CHAIN_RATIO = 0.9
TOLERANCE = 0.10
TOLERANCE_ESTIMATED = 0.25
LATE_AFTER_DAYS = 3


def user_schedules(db: Session, user: User) -> list[IncomeSchedule]:
    return list(
        db.scalars(
            select(IncomeSchedule)
            .where(IncomeSchedule.user_id == user.id)
            .order_by(IncomeSchedule.created_at)
        )
    )


def apply_schedule(db: Session, user_id: str, schedule: IncomeSchedule, valid) -> None:
    """Write a validated `IncomeScheduleIn` onto the row; the payer name is
    resolved to a payee (find-or-create, design D3), empty clears it."""
    data = valid.model_dump()
    for f in SCHEDULE_FIELDS:
        setattr(schedule, f, data.get(f))
    if schedule.estimated is None:
        schedule.estimated = False
    payee = resolve_payee(db, user_id, data.get("payer"))
    schedule.payee_id = payee.id if payee else None
    schedule.payee = payee


def expected_in(schedules: list[IncomeSchedule], month: str) -> int:
    return sched.payments_in(schedules, month)


def yearly_cents(schedule: IncomeSchedule, month: str | None = None) -> int:
    start = sched.month_index(month or sched.current_month())
    return sum(
        schedule.amount_cents
        for i in range(start, start + 12)
        if sched.occurs(schedule, sched.month_from_index(i))
    )


def _due_date(month: str, day: int | None) -> date:
    """The occurrence's date; a missing day counts as the month's last day."""
    year, mon = (int(p) for p in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return date(year, mon, min(day or last, last))


@dataclass
class _Occurrence:
    schedule: IncomeSchedule
    due: date
    received: int = 0
    transaction_ids: list[str] = field(default_factory=list)

    @property
    def is_received(self) -> bool:
        return bool(self.transaction_ids)


def _assign(inflow: Transaction, covered: list[_Occurrence]) -> None:
    """One inflow, whole, over one or more occurrences; the last takes the difference."""
    rest = inflow.amount_cents
    for occ in covered[:-1]:
        occ.received += occ.schedule.amount_cents
        rest -= occ.schedule.amount_cents
        occ.transaction_ids.append(inflow.id)
    covered[-1].received += rest
    covered[-1].transaction_ids.append(inflow.id)


def _fits(occ: _Occurrence, amount: int) -> bool:
    expected = occ.schedule.amount_cents
    tolerance = TOLERANCE_ESTIMATED if occ.schedule.estimated else TOLERANCE
    return abs(amount - expected) <= tolerance * expected


def month_income(db: Session, user: User, month: str) -> MonthIncomeView:
    schedules = user_schedules(db, user)
    occurrences = sorted(
        (
            _Occurrence(schedule=s, due=_due_date(month, s.day))
            for s in schedules
            if sched.occurs(s, month)
        ),
        key=lambda o: (o.due, o.schedule.created_at),
    )

    start, end = month_bounds(month)
    inflows = list(
        db.scalars(
            select(Transaction)
            .where(
                *income_filters(user),
                Transaction.date >= start,
                Transaction.date < end,
                Transaction.source != "opening_balance",
            )
            .order_by(Transaction.date, Transaction.created_at)
        )
    )

    # Pass 1: by payee.
    unmatched: list[Transaction] = []
    for inflow in inflows:
        open_ = [
            o
            for o in occurrences
            if inflow.payee_id and o.schedule.payee_id == inflow.payee_id and not o.is_received
        ]
        if not open_:
            unmatched.append(inflow)
            continue
        covered = [open_[0]]
        total = open_[0].schedule.amount_cents
        for nxt in open_[1:]:
            if inflow.amount_cents < CHAIN_RATIO * (total + nxt.schedule.amount_cents):
                break
            covered.append(nxt)
            total += nxt.schedule.amount_cents
        _assign(inflow, covered)

    # Pass 2: by amount, for schedules without payee.
    unplanned: list[Transaction] = []
    for inflow in unmatched:
        fits = [
            o
            for o in occurrences
            if o.schedule.payee_id is None
            and not o.is_received
            and _fits(o, inflow.amount_cents)
        ]
        if not fits:
            unplanned.append(inflow)
            continue
        best = min(
            fits,
            key=lambda o: (
                abs(inflow.amount_cents - o.schedule.amount_cents),
                abs((inflow.date - o.due).days),
            ),
        )
        _assign(inflow, [best])

    today = clock.today_madrid()
    current = today.strftime("%Y-%m")
    late_before = today - timedelta(days=LATE_AFTER_DAYS)

    def status(occ: _Occurrence) -> str:
        if occ.is_received:
            return "received"
        if month < current:
            return "missed"
        if month == current and occ.due < late_before:
            return "late"
        return "pending"

    result = []
    for occ in occurrences:
        s = occ.schedule
        st = status(occ)
        result.append(
            IncomeOccurrence(
                schedule_id=s.id,
                name=s.name,
                payee_id=s.payee_id,
                payer=s.payer,
                day=s.day,
                amount_cents=s.amount_cents,
                estimated=s.estimated,
                received_cents=occ.received,
                difference_cents=occ.received - s.amount_cents if st == "received" else None,
                status=st,
                transaction_ids=occ.transaction_ids,
            )
        )

    return MonthIncomeView(
        month=month,
        has_schedules=bool(schedules),
        occurrences=result,
        unplanned=[
            UnplannedIncome(
                transaction_id=t.id,
                payee_id=t.payee_id,
                label=t.payee_name or t.description or "",
                date=t.date,
                amount_cents=t.amount_cents,
            )
            for t in unplanned
        ],
        expected_cents=sum(o.amount_cents for o in result),
        received_cents=sum(t.amount_cents for t in inflows),
        still_expected_cents=sum(
            o.amount_cents for o in result if o.status in ("pending", "late")
        ),
    )
