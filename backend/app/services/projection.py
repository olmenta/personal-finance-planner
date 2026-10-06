"""Upcoming payments projection and annual plan (category-targets D6–D7).

Port of the approved prototype's `simulate`: each future month allocates its
expected income — the month's income-schedule occurrences, never probable
money — in priority order —
(1) payments due that month, (2) day-to-day budgets, (3) catch-up set-asides
for later payments, (4) undated goals — pro-rata within a level that doesn't
fit, leftovers carried unassigned. Month M itself reports the overview's
real coverage; its income still due (pending or late) carries into M+1.
Nothing here moves money; it is recomputed on every read.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import PaymentSchedule, User
from ..schemas import (
    PlanSummary,
    UpcomingMonth,
    UpcomingOccurrence,
    UpcomingView,
)
from . import income as income_service
from . import schedules as sched
from .budget_view import build_view
from .overview import build_overview


def _allocate(wanted: dict[str, float], money: float) -> tuple[dict[str, float], float]:
    total = sum(wanted.values())
    if total <= 0:
        return {k: 0.0 for k in wanted}, money
    ratio = min(1.0, max(0.0, money) / total)
    return {k: v * ratio for k, v in wanted.items()}, money - total * ratio


def _is_goal_only(schedules: list[PaymentSchedule]) -> bool:
    return bool(schedules) and all(s.pattern == "no_date" for s in schedules)


@dataclass
class _Plan:
    names: dict[str, str]
    dated: dict[str, list[PaymentSchedule]]  # categories with dated payments
    goals: dict[str, list[PaymentSchedule]]  # categories with only undated goals
    flexible_budget: dict[str, int]  # current month's day-to-day assignments


def _plan(db: Session, user: User, month: str) -> tuple[_Plan, object]:
    view = build_view(db, user, month)
    by_category = sched.schedules_by_category(db, user)
    names, dated, goals, flexible = {}, {}, {}, {}
    for g in view.groups:
        for c in g.categories:
            names[c.id] = c.name
            schedules = by_category.get(c.id, [])
            if _is_goal_only(schedules):
                goals[c.id] = schedules
            elif schedules:
                dated[c.id] = schedules
            elif c.kind == "flexible":
                flexible[c.id] = max(0, c.assigned_cents)
    return _Plan(names, dated, goals, flexible), view


def _occurrences(
    plan: _Plan, month: str, available: dict[str, float] | None
) -> list[UpcomingOccurrence]:
    """This month's payments; with `available`, mark coverage in day order."""
    result = []
    for category_id, schedules in plan.dated.items():
        reserve = available.get(category_id, 0.0) if available is not None else None
        due = sorted((s for s in schedules if sched.occurs(s, month)), key=lambda s: s.day or 1)
        for s in due:
            covered = short = None
            if reserve is not None:
                got = max(0.0, min(float(s.amount_cents), reserve))
                short = round(s.amount_cents - got)
                covered = short == 0
                reserve -= s.amount_cents
            result.append(
                UpcomingOccurrence(
                    category_id=category_id,
                    category_name=plan.names.get(category_id, ""),
                    schedule_id=s.id,
                    name=s.name,
                    day=s.day,
                    amount_cents=s.amount_cents,
                    estimated=s.estimated,
                    covered=covered,
                    short_cents=short,
                )
            )
    return sorted(result, key=lambda o: o.day or 1)


def upcoming(db: Session, user: User, month: str) -> UpcomingView:
    plan, view = _plan(db, user, month)
    overview = build_overview(db, user, month)
    incomes = income_service.user_schedules(db, user)
    income_known = bool(incomes)
    flexible_budget = sum(plan.flexible_budget.values())

    # Month M: the overview's real coverage.
    pending_short = {p.schedule_id: p.short_cents for p in overview.to_pay}
    first = []
    for occ in _occurrences(plan, month, None):
        short = pending_short.get(occ.schedule_id, 0)
        first.append(occ.model_copy(update={"covered": short == 0, "short_cents": short}))
    assigned = {c.id: c.assigned_cents for g in view.groups for c in g.categories}
    rollover = {c.id: c.rollover_cents for g in view.groups for c in g.categories}
    wanted_m = sum(
        sched.amounts(s, month, rollover.get(cid, 0))[2]
        for cid, s in [*plan.dated.items(), *plan.goals.items()]
    )
    funded_m = sum(max(0, assigned.get(cid, 0)) for cid in list(plan.dated) + list(plan.goals))
    months = [
        UpcomingMonth(
            month=month,
            expected_income_cents=income_service.expected_in(incomes, month)
            if income_known
            else None,
            occurrences=first,
            payments_cents=sum(o.amount_cents for o in first),
            short_cents=sum(o.short_cents or 0 for o in first),
            flexible_budget_cents=flexible_budget,
            flexible_funded_cents=flexible_budget,
            set_aside_wanted_cents=wanted_m,
            set_aside_funded_cents=min(funded_m, wanted_m),
            unassigned_cents=max(0, overview.to_be_assigned_cents),
        )
    ]

    # Projected end of M.
    saved: dict[str, float] = {cid: 0.0 for cid in [*plan.dated, *plan.goals]}
    for item in overview.saved.items:
        if item.category_id in saved:
            saved[item.category_id] = float(item.amount_cents)
    tba = float(max(0, overview.to_be_assigned_cents))
    if income_known:
        tba += income_service.month_income(db, user, month).still_expected_cents

    start = sched.month_index(month)
    for index in range(start + 1, start + 12):
        m = sched.month_from_index(index)
        if not income_known:
            occ = _occurrences(plan, m, None)
            months.append(
                UpcomingMonth(
                    month=m, occurrences=occ, payments_cents=sum(o.amount_cents for o in occ)
                )
            )
            continue
        expected = income_service.expected_in(incomes, m)
        money = expected + tba
        pay = {cid: float(sched.payments_in(s, m)) for cid, s in plan.dated.items()}
        need_now = {cid: max(0.0, pay[cid] - saved[cid]) for cid in plan.dated}
        quota = {
            cid: max(sched.category_normal(s, m), sched.catch_up(s, m, round(saved[cid])))
            for cid, s in plan.dated.items()
        }
        later = {cid: max(0.0, quota[cid] - need_now[cid]) for cid in plan.dated}
        goal_wanted = {cid: sched.category_normal(s, m) for cid, s in plan.goals.items()}

        a1, money = _allocate(need_now, money)
        a2, money = _allocate({k: float(v) for k, v in plan.flexible_budget.items()}, money)
        a3, money = _allocate(later, money)
        a4, money = _allocate(goal_wanted, money)

        available = {cid: saved[cid] + a1[cid] + a3[cid] for cid in plan.dated}
        occ = _occurrences(plan, m, available)
        uncovered = 0.0
        for cid in plan.dated:
            end = available[cid] - pay[cid]
            if end < 0:
                uncovered += -end
            saved[cid] = max(0.0, end)
        for cid in plan.goals:
            saved[cid] += a4[cid]
        unassigned = max(0.0, money)
        tba = unassigned - uncovered

        months.append(
            UpcomingMonth(
                month=m,
                expected_income_cents=expected,
                occurrences=occ,
                payments_cents=sum(o.amount_cents for o in occ),
                short_cents=sum(o.short_cents or 0 for o in occ),
                flexible_budget_cents=flexible_budget,
                flexible_funded_cents=round(sum(a2.values())),
                set_aside_wanted_cents=round(sum(later.values()) + sum(goal_wanted.values())),
                set_aside_funded_cents=round(sum(a3.values()) + sum(a4.values())),
                unassigned_cents=round(unassigned),
            )
        )
    return UpcomingView(
        income_known=income_known,
        income_cents=sum(m.expected_income_cents or 0 for m in months) if income_known else None,
        months=months,
    )


def summary(db: Session, user: User, month: str) -> PlanSummary:
    plan, _ = _plan(db, user, month)
    incomes = income_service.user_schedules(db, user)
    start = sched.month_index(month)
    window = [sched.month_from_index(i) for i in range(start, start + 12)]
    scheduled = sum(sched.payments_in(s, m) for s in plan.dated.values() for m in window)
    goals = sum(s.amount_cents for ss in plan.goals.values() for s in ss) + sum(
        s.amount_cents for ss in plan.dated.values() for s in ss if s.pattern == "no_date"
    )
    # One-off payments beyond the window: the share that has to be set aside
    # during these 12 months (amount spread evenly until its month).
    for ss in plan.dated.values():
        for s in ss:
            if s.pattern != "once" or not s.once_month:
                continue
            target = sched.month_index(s.once_month)
            if target < start + 12:
                continue  # past, or already counted as a payment in the window
            months_left = target - start + 1
            goals += round(s.amount_cents * min(12, months_left) / months_left)
    flexible = sum(plan.flexible_budget.values()) * 12
    costs = scheduled + flexible + goals
    income_year = sum(income_service.expected_in(incomes, m) for m in window) if incomes else None
    gap = income_year - costs if income_year is not None else None
    return PlanSummary(
        month=month,
        income_known=bool(incomes),
        income_cents=income_year,
        scheduled_cents=scheduled,
        flexible_cents=flexible,
        goals_cents=goals,
        costs_cents=costs,
        gap_cents=gap,
        gap_monthly_cents=round(gap / 12) if gap is not None else None,
    )
