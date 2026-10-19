"""Home (spec: home, redesign-home-navigation design D1–D6).

Composes existing services into one versioned snapshot; never computes a
money amount of its own. The summary maps the month overview exactly
(M = T + L + F + U), the statuses say whether the numbers can be trusted,
and the coach proposals arrive as one priority action plus grouped causes.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account, Category, ImportBatch, Transaction, User
from ..schemas import (
    HomeData,
    HomeFuture,
    HomeGroup,
    HomeReason,
    HomeReasonItem,
    HomeSummary,
    HomeView,
)
from . import coach
from . import schedules as sched

STALE_AFTER_DAYS = 14  # proposed freshness threshold (design D3)

GROUPS = [  # (key, title, kinds) in display order of causes
    ("late", "Money that's late", {"late_income", "late_debt_payment"}),
    ("coming_up", "Coming up", {"short_months"}),
    ("adjustments", "Budget adjustments", {"overspending", "underspending"}),
    ("unassigned", "Money with no job", {"unassigned"}),
]


def _summary(overview) -> HomeSummary:
    return HomeSummary(
        accounts_cents=overview.accounts_cents,
        covered_cents=overview.covered_cents,
        left_to_spend_cents=overview.left_to_spend.total_cents - overview.overspent_cents,
        saved_cents=overview.saved.total_cents,
        unassigned_cents=overview.to_be_assigned_cents,
        paid_cents=overview.paid.total_cents,
        card_payments_cents=overview.card_payments.total_cents,
        still_to_pay_cents=overview.to_pay_total_cents,
        short_cents=sum(p.short_cents for p in overview.to_pay),
    )


def _reasons(overview, view) -> list[HomeReason]:
    reasons = []
    if overview.to_be_assigned_cents < 0:
        reasons.append(HomeReason(code="over_assigned", amount_cents=-overview.to_be_assigned_cents))
    categories = [c for g in view.groups for c in g.categories]
    over = [
        HomeReasonItem(category_id=c.id, name=c.name, amount_cents=-c.available_cents)
        for c in categories
        if c.kind == "flexible" and c.available_cents < 0
    ]
    if over:
        over.sort(key=lambda i: -i.amount_cents)
        reasons.append(HomeReason(code="overspent_categories",
                                  amount_cents=sum(i.amount_cents for i in over), items=over))
    card = sum(c.credit_overspent_cents for c in categories)
    if card > 0:
        reasons.append(HomeReason(code="unbudgeted_card_spending", amount_cents=card))
    short = sum(p.short_cents for p in overview.to_pay)
    if short > 0:
        reasons.append(HomeReason(code="uncovered_payments", amount_cents=short))
    return reasons


def _data(db: Session, user: User, view, income_known: bool) -> HomeData:
    last = db.scalar(
        select(func.max(Transaction.date)).where(
            Transaction.user_id == user.id, Transaction.status == "confirmed"
        )
    )
    pending = db.scalar(
        select(func.count()).select_from(ImportBatch).where(
            ImportBatch.user_id == user.id, ImportBatch.status == "staged"
        )
    )
    today = clock.today_madrid()
    stale = last is None or (today - last) > timedelta(days=STALE_AFTER_DAYS)
    uncategorized = view.uncategorized_count
    return HomeData(
        last_transaction_date=last,
        uncategorized_count=uncategorized,
        pending_import=bool(pending),
        income_known=income_known,
        limited=bool(uncategorized or pending or stale),
    )


def _future(db: Session, user: User, month: str, income_known: bool) -> HomeFuture:
    if not income_known:
        return HomeFuture(status="unknown")
    from .projection import upcoming

    for m in upcoming(db, user, month).months[1:]:
        short = m.short_cents or 0
        gap = max(0, (m.set_aside_wanted_cents or 0) - (m.set_aside_funded_cents or 0))
        if short > 0 or gap > 0:
            return HomeFuture(status="needs_attention", month=m.month,
                              short_cents=short, set_aside_gap_cents=gap)
    return HomeFuture(status="on_track")


def _groups(proposals: list) -> tuple:
    if not proposals:
        return None, []
    priority, rest = proposals[0], proposals[1:]
    groups = []
    for key, title, kinds in GROUPS:
        members = [p for p in rest if p.kind in kinds]
        if members:
            groups.append((min(p.urgency for p in members), key, title, members))
    groups.sort(key=lambda g: g[0])
    return priority, [
        HomeGroup(key=key, title=title, proposals=[coach.proposal_out(p) for p in members])
        for _, key, title, members in groups
    ]


def _is_set_up(db: Session, user: User) -> bool:
    """Setup done: the user has a budget (categories, from the onboarding or
    the starter template) or has recorded money. A freshly provisioned user,
    with only the empty cash account, has neither (spec: home, not_set_up)."""
    has_categories = db.scalar(select(Category.id).where(Category.user_id == user.id).limit(1))
    if has_categories:
        return True
    return db.scalar(select(Transaction.id).where(Transaction.user_id == user.id).limit(1)) is not None


def build_home(db: Session, user: User) -> HomeView:
    from .budget_view import build_view
    from .income import user_schedules
    from .overview import build_overview

    month = sched.current_month()
    generated_at = datetime.now(timezone.utc)
    has_accounts = bool(db.scalar(
        select(func.count()).select_from(Account).where(
            Account.user_id == user.id, Account.archived.is_(False)
        )
    ))
    overview = build_overview(db, user, month)
    view = build_view(db, user, month)
    income_known = bool(user_schedules(db, user))
    set_up = _is_set_up(db, user)
    reasons = _reasons(overview, view) if set_up else []
    if not set_up:
        status = "not_set_up"
    elif not has_accounts:
        status = "no_accounts"
    elif reasons:
        status = "needs_organizing"
    else:
        status = "organized"
    summary = _summary(overview)
    data = _data(db, user, view, income_known)
    future = _future(db, user, month, income_known)
    # Nothing to analyze before setup: no reasons, no suggestions.
    visible = coach.visible(db, user) if set_up else []
    priority, groups = _groups(visible)
    version_source = {
        "summary": summary.model_dump(),
        "status": status,
        "reasons": [r.model_dump() for r in reasons],
        "data": data.model_dump(mode="json"),
        "future": future.model_dump(),
        "proposals": [(p.fingerprint, p.revision) for p in visible],
    }
    snapshot = hashlib.sha256(
        json.dumps(version_source, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return HomeView(
        month=month,
        generated_at=generated_at,
        status=status,
        reasons=reasons,
        summary=summary,
        data=data,
        future=future,
        priority=coach.proposal_out(priority) if priority else None,
        groups=groups,
        snapshot_version=snapshot,
    )
