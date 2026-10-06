"""Payment schedules: occurrences and monthly amounts (category-targets D3).

Month-granular and pure — the day only orders payments and splits paid from
pending in the month overview. Amounts are float cents internally and
rounded at the edges: normal to the nearest cent, catch-up and the
suggested amount up to the cent (so a suggestion never under-funds).
"""

import math
from collections.abc import Iterable, Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import PaymentSchedule, User


# Catch-up looks at least 12 months ahead, and further when a one-off future
# payment is later than that (capped at 10 years) — saving for a future
# expense is spread over every month until it.
MIN_HORIZON = 12
MAX_HORIZON = 120


class ScheduleRule(Protocol):
    """The rule fields `occurs` reads — payment and income schedules alike."""

    amount_cents: int
    pattern: str
    months: list[int] | None
    month: int | None
    every_n: int | None
    start_month: str | None
    count: int | None
    once_month: str | None


def current_month() -> str:
    return clock.current_month()


def month_index(month: str) -> int:
    year, mon = (int(p) for p in month.split("-"))
    return year * 12 + mon - 1


def month_from_index(index: int) -> str:
    return f"{index // 12}-{index % 12 + 1:02d}"


def occurs(schedule: ScheduleRule, month: str) -> bool:
    m = month_index(month)
    mon = m % 12 + 1
    match schedule.pattern:
        case "monthly":
            if schedule.count is None:
                return True
            start = month_index(schedule.start_month or month)
            return start <= m < start + schedule.count
        case "some_months":
            return mon in (schedule.months or [])
        case "annual":
            return mon == schedule.month
        case "every_n":
            start = month_index(schedule.start_month or month)
            return m >= start and (m - start) % (schedule.every_n or 1) == 0
        case "once":
            return schedule.once_month == month
        case _:  # no_date: an annual goal, never due
            return False


def payments_in(schedules: Iterable[ScheduleRule], month: str) -> int:
    """Money that moves in `month`: leaves a category, or arrives as income."""
    return sum(s.amount_cents for s in schedules if occurs(s, month))


def horizon_end(schedules: Sequence[PaymentSchedule], start: int) -> int:
    """Last month index (inclusive) the catch-up must look at."""
    end = start + MIN_HORIZON - 1
    for s in schedules:
        if s.pattern == "once" and s.once_month:
            end = max(end, month_index(s.once_month))
    return min(end, start + MAX_HORIZON - 1)


def normal_amount(schedule: PaymentSchedule, month: str) -> float:
    a = schedule.amount_cents
    match schedule.pattern:
        case "monthly":
            if schedule.count is None:
                return a
            return a if occurs(schedule, month) else 0
        case "some_months":
            return a * len(schedule.months or []) / 12
        case "annual" | "no_date":
            return a / 12
        case "every_n":
            return a / (schedule.every_n or 1)
        case _:  # once: covered by the catch-up amount
            return 0


def category_normal(schedules: Sequence[PaymentSchedule], month: str) -> float:
    return sum(normal_amount(s, month) for s in schedules)


def catch_up(schedules: Sequence[PaymentSchedule], month: str, saved: int) -> float:
    """Minimum constant monthly set-aside, given `saved`, so no payment —
    however far ahead — goes uncovered."""
    start = month_index(month)
    cumulative = 0
    best = 0.0
    for j in range(start, horizon_end(schedules, start) + 1):
        cumulative += payments_in(schedules, month_from_index(j))
        if cumulative > 0:
            best = max(best, (cumulative - saved) / (j - start + 1))
    return max(0.0, best)


def amounts(
    schedules: Sequence[PaymentSchedule], month: str, saved: int
) -> tuple[int, int, int]:
    """(normal_cents, catch_up_cents, suggested_cents) for one category."""
    normal = category_normal(schedules, month)
    needed = catch_up(schedules, month, saved)
    return round(normal), math.ceil(needed - 1e-9), math.ceil(max(normal, needed) - 1e-9)


def schedules_by_category(db: Session, user: User) -> dict[str, list[PaymentSchedule]]:
    result: dict[str, list[PaymentSchedule]] = {}
    for schedule in db.scalars(
        select(PaymentSchedule)
        .where(PaymentSchedule.user_id == user.id)
        .order_by(PaymentSchedule.created_at)
    ):
        result.setdefault(schedule.category_id, []).append(schedule)
    return result


def effective_kind(stored_kind: str, schedules: Sequence[PaymentSchedule]) -> str:
    """Any payment makes a category scheduled; otherwise the savings flag."""
    if schedules:
        return "scheduled"
    return "savings" if stored_kind == "savings" else "flexible"
