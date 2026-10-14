"""Coach proposals (spec: coach-proposals, design D1–D4).

Pure rules over data the app already computes — budget views, the month
overview, the projection, expected income — each producing one proposal
with exact numbers, plain-language copy and one action. No LLM: nothing
here leaves the app. State (dismissed for a week, accepted) is kept per
fingerprint, never with amounts.
"""

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..models import CoachProposalState, User
from . import schedules as sched

MIN_DIFF_CENTS = 1_000
ROUND_TO_CENTS = 500
HISTORY_MONTHS = 3
OVERSPENT_MIN_MONTHS = 2
UNDERSPENT_MIN_MONTHS = 3
DISMISS_DAYS = 7
MAX_SOURCES = 3

URGENCY = {
    "late_income": 0,
    "late_debt_payment": 1,
    "short_months": 2,
    "overspending": 3,
    "unassigned": 4,
    "underspending": 5,
}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class CoachError(Exception):
    def __init__(self, status: int, code: str, proposal: "Proposal | None" = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.proposal = proposal  # proposal_changed: the current version


@dataclass
class Proposal:
    fingerprint: str
    kind: str
    title: str
    body: str
    action: str  # raise | lower | add_income | link_income | open
    amount_cents: int = 0
    payload: dict = field(default_factory=dict)

    @property
    def urgency(self) -> int:
        return URGENCY[self.kind]

    @property
    def revision(self) -> str | None:
        """Binds acceptance to the reviewed amounts (redesign F02): any change
        in what a raise or lower would do yields a new revision."""
        if self.action not in ("raise", "lower"):
            return None
        d = self.payload
        sources = ",".join(sorted(s["category_id"] for s in d.get("sources") or []))
        raw = (f"{self.fingerprint}|{d['category_id']}|{d['current_cents']}|"
               f"{d['suggested_cents']}|{d['diff_cents']}|{sources}")
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def eur(cents: int) -> str:
    """es-ES euro format, like the webapp's euroCents: 1.234,50 €."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole:,}".replace(",", ".") + f",{frac:02d} €"


def ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return f"{day}th"
    return f"{day}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th') }"


def month_name(month: str) -> str:
    return MONTH_NAMES[int(month[5:7]) - 1]


def fingerprint(kind: str, subject: str, month: str) -> str:
    return f"{kind}:{subject}:{month}"


def round_up(cents: float) -> int:
    return int(math.ceil(cents / ROUND_TO_CENTS - 1e-9) * ROUND_TO_CENTS)


def proposal_out(p: Proposal) -> "CoachProposalOut":
    from ..schemas import CoachProposalOut

    data = p.payload
    return CoachProposalOut(
        fingerprint=p.fingerprint,
        revision=p.revision,
        kind=p.kind,  # type: ignore[arg-type]
        title=p.title,
        body=p.body,
        action=p.action,  # type: ignore[arg-type]
        amount_cents=p.amount_cents,
        category_id=data.get("category_id"),
        current_cents=data.get("current_cents"),
        suggested_cents=data.get("suggested_cents"),
        diff_cents=data.get("diff_cents"),
        sources=data.get("sources"),
        schedule_id=data.get("schedule_id"),
        payer=data.get("payer"),
        href=data.get("href"),
    )


# ---- Detectors --------------------------------------------------------------------------


def _late_income(db: Session, user: User, month: str) -> list[Proposal]:
    from .income import month_income

    result = []
    for occ in month_income(db, user, month).occurrences:
        if occ.status != "late":
            continue
        day = f"on the {ordinal(occ.day)} " if occ.day else ""
        result.append(Proposal(
            fingerprint=fingerprint("late_income", occ.schedule_id, month),
            kind="late_income",
            title=f"Your {occ.name} isn't here yet",
            body=f"It usually arrives {day}({eur(occ.amount_cents)}). If it came in, add it; "
                 "if it's already recorded, link it.",
            action="add_income",
            amount_cents=occ.amount_cents,
            payload={"schedule_id": occ.schedule_id, "payer": occ.payer,
                     "amount_cents": occ.amount_cents},
        ))
    return result


def _late_debt_payments(overview, month: str) -> list[Proposal]:
    result = []
    for p in overview.to_pay:
        if not p.late:
            continue
        due = f"It was due on the {ordinal(p.day)} and" if p.day else "It"
        result.append(Proposal(
            fingerprint=fingerprint("late_debt_payment", p.schedule_id, month),
            kind="late_debt_payment",
            title=f"Your {p.category_name} payment is late",
            body=f"{due} hasn't gone out yet ({eur(p.amount_cents)}).",
            action="open",
            amount_cents=p.amount_cents,
            payload={"href": "/debts"},
        ))
    return result


def _short_months(db: Session, user: User, month: str) -> list[Proposal]:
    from .projection import upcoming

    view = upcoming(db, user, month)
    if not view.income_known:
        return []
    short = [m for m in view.months[1:] if (m.short_cents or 0) > 0]
    if not short:
        return []
    first = short[0]
    names = [month_name(m.month) for m in short]
    label = names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"
    worst = next((o for o in first.occurrences if o.covered is False), None)
    detail = f" for {worst.category_name}" if worst else ""
    return [Proposal(
        fingerprint=fingerprint("short_months", first.month, month),
        kind="short_months",
        title=f"{label} won't be fully covered",
        body=f"{eur(first.short_cents or 0)} short{detail} in {month_name(first.month)}. "
             "Planning for it now is easier than in that month.",
        action="open",
        amount_cents=sum(m.short_cents or 0 for m in short),
        payload={"href": f"/future?month={first.month}", "months": [m.month for m in short]},
    )]


def _history(db: Session, user: User, month: str) -> list[dict]:
    """Per closed month (oldest first): category id → its view row. Months the
    user never opened are skipped (no assignments, no history)."""
    from .budget_view import build_view, get_budget_month

    start = sched.month_index(month)
    months = []
    for i in range(start - HISTORY_MONTHS, start):
        m = sched.month_from_index(i)
        if get_budget_month(db, user, m) is None:
            months.append(None)
            continue
        view = build_view(db, user, m)
        months.append({c.id: c for g in view.groups for c in g.categories})
    return months


def _sources(categories: list, exclude: str, needed: int) -> list[dict]:
    candidates = sorted(
        (c for c in categories
         if c.kind == "flexible" and c.id != exclude and c.available_cents >= needed),
        key=lambda c: -c.available_cents,
    )
    return [{"category_id": c.id, "name": c.name, "available_cents": c.available_cents}
            for c in candidates[:MAX_SOURCES]]


def _spending_proposals(current_view, history: list, month: str) -> list[Proposal]:
    if any(h is None for h in history) or len(history) < HISTORY_MONTHS:
        return []
    categories = [c for g in current_view.groups for c in g.categories]
    tba = current_view.to_be_assigned_cents
    result = []
    for c in categories:
        if c.kind != "flexible":
            continue
        rows = [h.get(c.id) for h in history]
        if any(r is None or r.kind != "flexible" for r in rows):
            continue
        spent = [r.spent_cents for r in rows]
        suggested = round_up(sum(spent) / len(spent))
        over = sum(1 for r in rows if r.available_cents < 0)
        under = sum(1 for r in rows if r.spent_cents < r.assigned_cents)
        current = c.assigned_cents
        if over >= OVERSPENT_MIN_MONTHS and suggested - current >= MIN_DIFF_CENTS:
            diff = suggested - current
            payload = {"category_id": c.id, "category_name": c.name,
                       "current_cents": current, "suggested_cents": suggested,
                       "diff_cents": diff}
            if diff > max(0, tba):
                payload["sources"] = _sources(categories, c.id, diff)
            result.append(Proposal(
                fingerprint=fingerprint("overspending", c.id, month),
                kind="overspending",
                title=f"{c.name} keeps going over",
                body=f"It went over in {over} of the last {HISTORY_MONTHS} months. You usually "
                     f"spend about {eur(suggested)}. Raise it from {eur(current)}?",
                action="raise",
                amount_cents=diff,
                payload=payload,
            ))
        elif under >= UNDERSPENT_MIN_MONTHS and current - suggested >= MIN_DIFF_CENTS:
            diff = current - suggested
            result.append(Proposal(
                fingerprint=fingerprint("underspending", c.id, month),
                kind="underspending",
                title=f"{c.name} always has money left",
                body=f"You've spent about {eur(suggested)} a month lately. Lower it from "
                     f"{eur(current)} and free {eur(diff)}?",
                action="lower",
                amount_cents=diff,
                payload={"category_id": c.id, "category_name": c.name,
                         "current_cents": current, "suggested_cents": suggested,
                         "diff_cents": diff},
            ))
    return result


def _unassigned(current_view, month: str) -> list[Proposal]:
    tba = current_view.to_be_assigned_cents
    if tba < MIN_DIFF_CENTS:
        return []
    return [Proposal(
        fingerprint=fingerprint("unassigned", "-", month),
        kind="unassigned",
        title=f"{eur(tba)} with no job yet",
        body="Give every euro a job: assign it to what's coming.",
        action="open",
        amount_cents=tba,
        payload={"href": "/budgets"},
    )]


def detect(db: Session, user: User, month: str | None = None) -> list[Proposal]:
    """Every proposal for the month, unfiltered by state, in urgency order."""
    from .budget_view import build_view
    from .overview import build_overview

    month = month or sched.current_month()
    current_view = build_view(db, user, month)
    overview = build_overview(db, user, month)
    proposals = [
        *_late_income(db, user, month),
        *_late_debt_payments(overview, month),
        *_short_months(db, user, month),
        *_spending_proposals(current_view, _history(db, user, month), month),
        *_unassigned(current_view, month),
    ]
    return sorted(proposals, key=lambda p: (p.urgency, -p.amount_cents))


# ---- State --------------------------------------------------------------------------------


def _now() -> datetime:
    today = clock.today_madrid()
    return datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)


def _states(db: Session, user: User) -> dict[str, CoachProposalState]:
    return {
        s.fingerprint: s
        for s in db.scalars(select(CoachProposalState).where(CoachProposalState.user_id == user.id))
    }


def visible(db: Session, user: User) -> list[Proposal]:
    states = _states(db, user)
    now = _now()

    def shown(p: Proposal) -> bool:
        s = states.get(p.fingerprint)
        if s is None:
            return True
        if s.state == "accepted":
            return False
        until = s.until if s.until is None or s.until.tzinfo else s.until.replace(tzinfo=timezone.utc)
        return until is not None and until <= now

    return [p for p in detect(db, user) if shown(p)]


def _record(db: Session, user: User, fp: str, state: str, until: datetime | None,
            revision: str | None = None) -> None:
    row = db.scalar(select(CoachProposalState).where(
        CoachProposalState.user_id == user.id, CoachProposalState.fingerprint == fp))
    if row is None:
        row = CoachProposalState(user_id=user.id, fingerprint=fp)
        db.add(row)
    row.state = state
    row.until = until
    row.revision = revision
    db.flush()


def _find(db: Session, user: User, fp: str) -> Proposal:
    proposal = next((p for p in visible(db, user) if p.fingerprint == fp), None)
    if proposal is None:
        raise CoachError(404, "proposal_not_found")
    return proposal


def dismiss(db: Session, user: User, fp: str) -> None:
    _find(db, user, fp)
    _record(db, user, fp, "dismissed", _now() + timedelta(days=DISMISS_DAYS))


def accept(db: Session, user: User, fp: str, revision: str,
           from_category_id: str | None) -> None:
    """Apply exactly the reviewed raise or lower (redesign F02, F03): the
    revision must match the recomputed proposal, a repeated acceptance is a
    no-op, and a funding source follows the budget's move rules."""
    from .budget_moves import MoveError, validate_source
    from .budget_view import build_view, ensure_assignment, materialize_month

    state = _states(db, user).get(fp)
    if state is not None and state.state == "accepted" and state.revision == revision:
        return  # retry of an applied acceptance
    proposal = _find(db, user, fp)
    if proposal.action not in ("raise", "lower"):
        raise CoachError(409, "not_acceptable")
    if proposal.revision != revision:
        raise CoachError(409, "proposal_changed", proposal)
    month = sched.current_month()
    data = proposal.payload
    bm = materialize_month(db, user, month)
    target = ensure_assignment(db, user, bm, data["category_id"])
    if target is None:
        raise CoachError(404, "proposal_not_found")
    diff = data["diff_cents"]
    if proposal.action == "raise":
        view = build_view(db, user, month)
        if from_category_id:
            try:
                source_view = validate_source(view, data["category_id"], from_category_id, diff)
            except MoveError as error:
                if error.code == "same_category":
                    raise CoachError(422, "same_category") from error
                raise CoachError(409, "not_enough_in_source") from error
            if source_view.kind != "flexible":
                # Savings, payments and card reserves are not free money.
                raise CoachError(409, "not_enough_in_source")
            source = ensure_assignment(db, user, bm, from_category_id)
            if source is None:
                raise CoachError(409, "not_enough_in_source")
            source.assigned_cents -= diff
            source.suggestion_state = "edited"
        elif diff > max(0, view.to_be_assigned_cents):
            raise CoachError(409, "not_enough_to_assign")
    target.assigned_cents = data["suggested_cents"]
    target.suggestion_state = "edited"
    db.flush()
    _record(db, user, fp, "accepted", None, revision)

