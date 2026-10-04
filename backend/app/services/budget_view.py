"""Budget month derivation — the single seam for all computed values.

available(c, M)      = assigned + rollover − spent
rollover(c, M)       = max(0, available(c, M−1))      overspending resets…
overspent(M)         = Σ max(0, −available(c, M))
to_be_assigned(M)    = TBA(M−1) + unbudgeted(M) − Σ assigned(M) − cash_overspent(M−1)
                                                     …cash part paid from TBA
TBA(start−1)         = signed sum of cash/bank activity before the budget start

Transfer rows (`transfer_pair_id`) never enter the budget plane. Credit
cards follow YNAB (accounts-and-transfers design D6): card spending counts
in its category at purchase and the funded part moves — derived, never
stored — to the card's payment category:

pool(c)              = max(0, assigned + rollover − cash_spent + card_refunds)
funded(c, K)         = min(card_spend(c, K), pool left)   cards in creation order
move(c → Pago K)     = funded(c, K) − card_refunds(c, K)
credit_overspent(c)  = Σ card_spend − Σ funded            stays as card debt
available(Pago K)    = assigned + rollover + Σ moves − payments(K)

Uncategorized non-transfer rows on a card (e.g. its opening debt) are card
debt, never To Be Assigned. One forward pass over calendar months from the
first materialized month; unopened months count as zero assignments and are
never materialized here.
Invariant: TBA(M) + Σ available(M) + Σ credit_overspent(M) = Σ confirmed
cash/bank activity up to the end of M. Nothing here is persisted.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import (
    Account,
    BudgetAssignment,
    BudgetMonth,
    Category,
    CategoryGroup,
    Transaction,
    User,
)
from ..schemas import (
    BudgetCategoryView,
    BudgetGroupView,
    BudgetMonthView,
    CoverSuggestion,
)
from . import schedules as sched


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
    """Lazily create the month. Scheduled categories draft their computed
    monthly amount (category-targets D4); the rest copy the previous month."""
    existing = get_budget_month(db, user, month)
    if existing is not None:
        return existing
    saved = month_chain(db, user, month).rollover
    by_category = sched.schedules_by_category(db, user)

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
        category_schedules = by_category.get(category.id, [])
        if category_schedules:
            # Computed, not a draft: categories with payments are assigned
            # exactly their monthly amount (never typed by hand).
            _, _, suggested = sched.amounts(
                category_schedules, month, saved.get(category.id, 0)
            )
            db.add(
                BudgetAssignment(
                    budget_month_id=bm.id,
                    category_id=category.id,
                    assigned_cents=suggested,
                    suggestion_cents=suggested,
                    suggestion_state="confirmed",
                )
            )
            continue
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


def ensure_assignment(
    db: Session, user: User, bm: BudgetMonth, category_id: str
) -> BudgetAssignment | None:
    """The month's assignment row for a category, created on demand for a
    category added after the month was materialized (PUT upserts, spec:
    budget-api). None when the category isn't the user's or is archived."""
    assignment = db.scalar(
        select(BudgetAssignment).where(
            BudgetAssignment.budget_month_id == bm.id,
            BudgetAssignment.category_id == category_id,
        )
    )
    if assignment is not None:
        return assignment
    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user.id,
            Category.archived.is_(False),
        )
    )
    if category is None:
        return None
    assignment = BudgetAssignment(
        budget_month_id=bm.id,
        category_id=category.id,
        assigned_cents=0,
        suggestion_cents=None,
        suggestion_state="confirmed",
    )
    db.add(assignment)
    db.flush()
    db.refresh(bm)
    return assignment


def refresh_computed_assignments(db: Session, user: User, category_id: str) -> None:
    """After a payment changes, re-set the category's assignment to its
    computed monthly amount in the current and later materialized months
    (past months keep their history). Months are walked in order so each
    one sees the previous month's updated balance."""
    schedules = sched.schedules_by_category(db, user).get(category_id, [])
    if not schedules:
        return  # back to day-to-day: keep what's assigned
    months = db.scalars(
        select(BudgetMonth)
        .where(BudgetMonth.user_id == user.id, BudgetMonth.month >= sched.current_month())
        .order_by(BudgetMonth.month)
    )
    for bm in months:
        assignment = ensure_assignment(db, user, bm, category_id)
        if assignment is None:
            return
        saved = month_chain(db, user, bm.month).rollover.get(category_id, 0)
        _, _, suggested = sched.amounts(schedules, bm.month, saved)
        assignment.assigned_cents = suggested
        assignment.suggestion_cents = suggested
        assignment.suggestion_state = "confirmed"
        db.flush()


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
            Transaction.transfer_pair_id.is_(None),
        )
        .group_by(Transaction.category_id)
    ).all()
    return {category_id: -total for category_id, total in rows if category_id}


def budget_account_ids(user: User):
    """Cash and bank accounts — the money To Be Assigned is made of. Credit
    accounts hold debt, not money (design D6)."""
    return select(Account.id).where(Account.user_id == user.id, Account.type != "credit")


def income_filters(user: User) -> tuple:
    """What counts as income: confirmed, positive, uncategorized, not a
    transfer twin, on a cash/bank account — a categorized inflow is a refund
    (category activity) and a credit account's opening balance is debt.
    Shared with the summary so dashboard and budget can never disagree."""
    return (
        Transaction.user_id == user.id,
        Transaction.status == "confirmed",
        Transaction.amount_cents > 0,
        Transaction.category_id.is_(None),
        Transaction.transfer_pair_id.is_(None),
        Transaction.account_id.in_(budget_account_ids(user)),
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
class MonthActivity:
    """One month's confirmed, non-transfer activity split by account kind."""

    cash_net: dict[str, int] = field(default_factory=dict)  # category -> signed
    card_spend: dict[str, dict[str, int]] = field(default_factory=dict)  # cat -> card -> cents
    card_refund: dict[str, dict[str, int]] = field(default_factory=dict)  # cat -> card -> cents
    payments: dict[str, int] = field(default_factory=dict)  # card -> net transfers in
    unbudgeted: int = 0  # signed uncategorized cash/bank activity


@dataclass
class MonthResult:
    spent: dict[str, int]
    available: dict[str, int]
    credit_overspent: dict[str, int]


@dataclass
class CardSetup:
    order: list[str]  # credit account ids, creation order
    payment_category: dict[str, str]  # credit account id -> payment category id


def card_setup(db: Session, user: User) -> CardSetup:
    order = list(
        db.scalars(
            select(Account.id)
            .where(Account.user_id == user.id, Account.type == "credit")
            .order_by(Account.created_at, Account.id)
        )
    )
    payment_category = {
        account_id: category_id
        for category_id, account_id in db.execute(
            select(Category.id, Category.payment_account_id).where(
                Category.user_id == user.id, Category.payment_account_id.is_not(None)
            )
        )
    }
    return CardSetup(order=order, payment_category=payment_category)


def month_math(
    assigned: dict[str, int],
    rollover: dict[str, int],
    act: MonthActivity,
    cards: CardSetup,
) -> MonthResult:
    """Spent / available / credit overspending for one month (design D6).

    Cash activity is applied first, so card spending is what ends up
    overspent — a month-level simplification of YNAB's chronological rule.
    """
    categories = (
        assigned.keys()
        | rollover.keys()
        | act.cash_net.keys()
        | act.card_spend.keys()
        | act.card_refund.keys()
        | set(cards.payment_category.values())
    )
    spent: dict[str, int] = {}
    available: dict[str, int] = {}
    credit_overspent: dict[str, int] = {}
    moves: dict[str, int] = {}  # card -> money moved into its payment category
    rank = {card: i for i, card in enumerate(cards.order)}
    for category_id in categories:
        cash_spent = -act.cash_net.get(category_id, 0)
        spends = act.card_spend.get(category_id, {})
        refunds = act.card_refund.get(category_id, {})
        base = assigned.get(category_id, 0) + rollover.get(category_id, 0)
        pool = max(0, base - cash_spent + sum(refunds.values()))
        unfunded = 0
        for card in sorted(spends, key=lambda k: (rank.get(k, len(rank)), k)):
            funded = min(spends[card], pool)
            pool -= funded
            unfunded += spends[card] - funded
            moves[card] = moves.get(card, 0) + funded
        for card, refund in refunds.items():
            moves[card] = moves.get(card, 0) - refund
        spent[category_id] = cash_spent + sum(spends.values()) - sum(refunds.values())
        available[category_id] = base - spent[category_id]
        if unfunded:
            credit_overspent[category_id] = unfunded
    for card, category_id in cards.payment_category.items():
        payments = act.payments.get(card, 0)
        spent[category_id] += payments
        available[category_id] += moves.get(card, 0) - payments
    return MonthResult(spent=spent, available=available, credit_overspent=credit_overspent)


def _activity_by_month(
    db: Session, user: User, range_start: date, range_end: date, credit: set[str]
) -> dict[str, MonthActivity]:
    """One grouped query: month × category × account × sign × transfer."""
    month_col = func.to_char(Transaction.date, "YYYY-MM")
    positive = case((Transaction.amount_cents > 0, True), else_=False)
    is_transfer = Transaction.transfer_pair_id.is_not(None)
    result: dict[str, MonthActivity] = {}
    for m, category_id, account_id, is_positive, transfer, total in db.execute(
        select(
            month_col,
            Transaction.category_id,
            Transaction.account_id,
            positive,
            is_transfer,
            func.sum(Transaction.amount_cents),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.date >= range_start,
            Transaction.date < range_end,
        )
        .group_by(month_col, Transaction.category_id, Transaction.account_id, positive, is_transfer)
    ):
        act = result.setdefault(m, MonthActivity())
        total = int(total)
        on_card = account_id in credit
        if transfer:
            if on_card:
                act.payments[account_id] = act.payments.get(account_id, 0) + total
        elif category_id is None:
            if not on_card:
                act.unbudgeted += total
        elif not on_card:
            act.cash_net[category_id] = act.cash_net.get(category_id, 0) + total
        elif is_positive:
            by_card = act.card_refund.setdefault(category_id, {})
            by_card[account_id] = by_card.get(account_id, 0) + total
        else:
            by_card = act.card_spend.setdefault(category_id, {})
            by_card[account_id] = by_card.get(account_id, 0) - total
    return result


@dataclass
class MonthChain:
    """Where month M starts: per-category rollover and the TBA carry-in —
    plus month M's own activity, so the view needs no second pass."""

    rollover: dict[str, int]
    reset: dict[str, int]  # per-category overspending of M−1 that didn't carry
    carried_in: int  # TBA(M−1)
    overspent_deducted: int  # cash overspending of M−1
    unbudgeted: int  # signed uncategorized cash/bank activity in M
    activity: MonthActivity
    cards: CardSetup


def month_chain(db: Session, user: User, month: str) -> MonthChain:
    """Forward pass from the budget start to `month` (design D1–D5).

    A few grouped queries over the whole range, then a pass in Python.
    """
    first = db.scalar(select(func.min(BudgetMonth.month)).where(BudgetMonth.user_id == user.id))
    start = first if first is not None and first < month else month
    range_start, _ = month_bounds(start)
    _, range_end = month_bounds(month)

    cards = card_setup(db, user)
    activity = _activity_by_month(db, user, range_start, range_end, set(cards.order))
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
            Transaction.account_id.in_(budget_account_ids(user)),
        )
    )

    rollover: dict[str, int] = {}
    reset: dict[str, int] = {}
    tba = int(pre_start or 0)
    overspent_prev = 0
    for index in range(_month_index(start), _month_index(month)):
        m = _month_from_index(index)
        m_assigned = assigned.get(m, {})
        act = activity.get(m, MonthActivity())
        tba += act.unbudgeted - sum(m_assigned.values()) - overspent_prev
        result = month_math(m_assigned, rollover, act, cards)
        overspent_prev = 0
        reset = {}
        next_rollover: dict[str, int] = {}
        for category_id, available in result.available.items():
            if available < 0:
                reset[category_id] = -available
                # The credit part stays on the card as debt; only the cash
                # part is paid from next month's To Be Assigned.
                credit = min(-available, result.credit_overspent.get(category_id, 0))
                overspent_prev += -available - credit
            next_rollover[category_id] = max(0, available)
        rollover = next_rollover

    current = activity.get(month, MonthActivity())
    return MonthChain(
        rollover=rollover,
        reset=reset,
        carried_in=tba,
        overspent_deducted=overspent_prev,
        unbudgeted=current.unbudgeted,
        activity=current,
        cards=cards,
    )


def cover_suggestions(
    available: dict[str, int], to_be_assigned: int, protected: set[str] | None = None
) -> dict[str, CoverSuggestion]:
    """Greedy cover sources, largest overspending first (design D7).

    Positive TBA first, then the non-overspent category with the most
    available; sources are consumed so two suggestions never share euros.
    `protected` categories (card payment money) are never donors.
    """
    overspent = sorted(
        ((cid, -a) for cid, a in available.items() if a < 0), key=lambda item: -item[1]
    )
    tba_left = max(0, to_be_assigned)
    donors = {
        cid: a for cid, a in available.items() if a > 0 and cid not in (protected or set())
    }
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
    chain = month_chain(db, user, month)
    rollover = chain.rollover
    assigned_by_category = {a.category_id: a.assigned_cents for a in bm.assignments}
    math = month_math(assigned_by_category, rollover, chain.activity, chain.cards)
    spent = math.spent
    payment_categories = {cid: acc for acc, cid in chain.cards.payment_category.items()}
    last_assigned, last_spent, avg_3m = quickfill_by_category(db, user, month)
    assignments = {a.category_id: a for a in bm.assignments}
    by_category = sched.schedules_by_category(db, user)

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
            available = math.available.get(category.id, assigned + cat_rollover - cat_spent)
            category_schedules = by_category.get(category.id, [])
            normal_cents = catch_up_cents = None
            if category_schedules:
                normal_cents, catch_up_cents, _ = sched.amounts(
                    category_schedules, month, cat_rollover
                )
            cat_views.append(
                BudgetCategoryView(
                    id=category.id,
                    name=category.name,
                    icon=category.icon,
                    kind=(
                        "credit_payment"
                        if category.id in payment_categories
                        else sched.effective_kind(category.kind, category_schedules)
                    ),  # type: ignore[arg-type]
                    payment_account_id=payment_categories.get(category.id),
                    normal_cents=normal_cents,
                    catch_up_cents=catch_up_cents,
                    assigned_cents=assigned,
                    spent_cents=cat_spent,
                    rollover_cents=cat_rollover,
                    available_cents=available,
                    overspent_cents=max(0, -available),
                    rollover_reset_cents=chain.reset.get(category.id, 0),
                    credit_overspent_cents=math.credit_overspent.get(category.id, 0),
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
        {c.id: c.available_cents for _, cats in rows for c in cats},
        to_be_assigned,
        protected=set(payment_categories),
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


def payment_available_by_card(db: Session, user: User, month: str) -> dict[str, int]:
    """credit account id -> its payment category's available in `month`,
    without materializing the month (an unopened month assigns nothing)."""
    chain = month_chain(db, user, month)
    if not chain.cards.payment_category:
        return {}
    bm = get_budget_month(db, user, month)
    assigned = {a.category_id: a.assigned_cents for a in bm.assignments} if bm else {}
    math = month_math(assigned, chain.rollover, chain.activity, chain.cards)
    return {
        card: math.available.get(category_id, 0)
        for card, category_id in chain.cards.payment_category.items()
    }
