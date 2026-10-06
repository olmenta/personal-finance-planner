"""Debts: what's owed, the paydown order and the debt-free date
(spec: debts, design D2 and D5).

Required payments are ordinary payment schedules (card plans, loan
installments, dated personal debts); this module only reads them. The pure
part — rates, order, plan for a target month, simulation — is mirrored in
webapp/src/lib/debts.ts for the editor's live preview.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..models import Account, Debt, DebtSettings, PaymentSchedule, Transaction, User
from . import schedules as sched

HORIZON_MONTHS = 120
CUSHION_MIN_CENTS = 30_000
CUSHION_MAX_CENTS = 100_000

# Order groups: a known rate first, then unknown, then personal without a rate.
KNOWN, UNKNOWN, INTEREST_FREE = 0, 1, 2


def monthly_rate(rate_bp: int | None, rate_period: str | None) -> float | None:
    """Monthly rate as a fraction; a yearly rate is divided by 12 (design D5)."""
    if rate_bp is None or rate_period not in ("month", "year"):
        return None
    rate = rate_bp / 10_000
    return rate if rate_period == "month" else rate / 12


def plan_for_target(owed_cents: int, rate: float | None, months: int) -> int:
    """Smallest monthly payment, rounded up to the cent, that pays `owed` off
    in `months` payments, interest included when a rate is known."""
    if owed_cents <= 0 or months < 1:
        return 0
    if not rate:
        return math.ceil(owed_cents / months - 1e-9)
    payment = owed_cents * rate / (1 - (1 + rate) ** -months)
    return math.ceil(payment - 1e-9)


@dataclass
class PlanDebt:
    """One debt as the simulation sees it."""

    id: str
    kind: str
    owed: float
    rate: float | None  # monthly fraction
    interest_free: bool = False  # personal without a rate
    # Required payment per month index (absolute month index → cents).
    required: dict[int, int] = field(default_factory=dict)
    # The monthly payment it frees for the next debt once paid off.
    roll_cents: int = 0
    end_index: int | None = None

    @property
    def order_key(self) -> tuple:
        if self.rate is not None:
            group = KNOWN
        elif self.interest_free:
            group = INTEREST_FREE
        else:
            group = UNKNOWN
        return (group, -(self.rate or 0.0), self.owed)


def order(debts: list[PlanDebt]) -> list[PlanDebt]:
    return sorted(debts, key=lambda d: d.order_key)


def simulate(debts: list[PlanDebt], extra_cents: int, start_index: int) -> None:
    """Month by month: required payments, then the extra plus the money freed
    by paid-off debts to the first debt in the order. Fills `end_index`."""
    ordered = order([d for d in debts if d.owed > 0.5])
    for d in debts:
        if d.owed <= 0.5:
            d.end_index = start_index
    freed = 0.0
    for m in range(start_index, start_index + HORIZON_MONTHS):
        active = [d for d in ordered if d.end_index is None]
        if not active:
            return
        pool = float(extra_cents) + freed
        for d in active:
            if d.rate and d.kind != "loan":  # loan installments already include it
                d.owed += d.owed * d.rate
            pay = min(d.owed, float(d.required.get(m, 0)))
            d.owed -= pay
            leftover = d.required.get(m, 0) - pay
            pool += leftover
        for d in active:
            if pool <= 0:
                break
            if d.owed <= 0.5:
                continue
            take = min(pool, d.owed)
            d.owed -= take
            pool -= take
        for d in active:
            if d.owed <= 0.5 and d.end_index is None:
                d.end_index = m
                # Its payment keeps working on the next debt from next month.
                freed += d.roll_cents


# ---- Reading the user's debts ----------------------------------------------------------


@dataclass
class DebtState:
    debt: Debt
    schedules: list[PaymentSchedule]
    owed: int
    required_monthly: int
    end_index: int | None = None
    paid_this_month: bool = False


def settings(db: Session, user: User) -> DebtSettings:
    row = db.get(DebtSettings, user.id)
    if row is None:
        row = DebtSettings(user_id=user.id, extra_monthly_cents=0)
        db.add(row)
        db.flush()
    return row


def user_debts(db: Session, user: User) -> list[Debt]:
    return list(
        db.scalars(select(Debt).where(Debt.user_id == user.id).order_by(Debt.created_at))
    )


def debt_for_category(db: Session, category_id: str) -> Debt | None:
    return db.scalar(select(Debt).where(Debt.category_id == category_id))


def card_account(db: Session, debt: Debt) -> Account | None:
    if debt.category.payment_account_id is None:
        return None
    return db.get(Account, debt.category.payment_account_id)


def card_owed_cents(balance: int, available: int, pending_plan: int) -> int:
    """What's still owed on a card: its debt minus the money set aside for new
    spending. This month's unpaid plan is in the payment category too, but it
    hasn't paid anything yet, so it doesn't count as set aside."""
    return max(0, -balance - max(0, available - pending_plan))


def paid_in_category_since(db: Session, user: User, category_id: str, since: datetime) -> int:
    """Confirmed net spending in the category from the debt's creation day on."""
    total = db.scalar(
        select(func.coalesce(func.sum(-Transaction.amount_cents), 0)).where(
            Transaction.user_id == user.id,
            Transaction.category_id == category_id,
            Transaction.status == "confirmed",
            Transaction.transfer_pair_id.is_(None),
            Transaction.date >= since.date(),
        )
    )
    return int(total or 0)


def loan_remaining(schedule: PaymentSchedule, month: str, paid_this_month: bool) -> tuple[int, int]:
    """(installments left, first unpaid month index) from `month` on."""
    current = sched.month_index(month)
    start = sched.month_index(schedule.start_month or month)
    last = start + (schedule.count or 1) - 1
    first = max(current, start)
    if paid_this_month and first == current and start <= current:
        first += 1
    return max(0, last - first + 1), first


def personal_owed(db: Session, user: User, debt: Debt) -> int:
    paid = paid_in_category_since(db, user, debt.category_id, debt.created_at)
    return max(0, (debt.owed_cents or 0) - paid)


def _occurrence_paid(schedules: list[PaymentSchedule], month: str, spent: int) -> bool:
    from .overview import match_payments  # overview imports budget_view; avoid a cycle

    match = match_payments(schedules, month, spent)
    return bool(match.occurrences) and all(o.paid for o in match.occurrences)


def build_debts_view(db: Session, user: User) -> "DebtsView":
    from ..schemas import DebtCushion, DebtOut, DebtsView
    from .accounts import balances
    from .budget_view import build_view

    month = sched.current_month()
    start = sched.month_index(month)
    view = build_view(db, user, month)
    cats = {c.id: c for g in view.groups for c in g.categories}
    by_category = sched.schedules_by_category(db, user)
    account_balances = balances(db, user.id)
    extra = settings(db, user).extra_monthly_cents

    plans: list[PlanDebt] = []
    rows: dict[str, dict] = {}
    for debt in user_debts(db, user):
        schedules = by_category.get(debt.category_id, [])
        c = cats.get(debt.category_id)
        spent = c.spent_cents if c else 0
        paid_now = bool(schedules) and _occurrence_paid(schedules, month, spent)
        rate = monthly_rate(debt.rate_bp, debt.rate_period)
        row: dict = {
            "id": debt.id,
            "kind": debt.kind,
            "category_id": debt.category_id,
            "account_id": None,
            "name": debt.category.name,
            "lender": None,
            "rate_bp": debt.rate_bp,
            "rate_period": debt.rate_period,
            "monthly_rate_bp": round(rate * 10_000, 2) if rate is not None else None,
            "minimum_cents": debt.minimum_cents,
            "below_minimum": None,
            "plan_monthly_cents": None,
            "installment_cents": None,
            "installments_left": None,
            "next_month": None,
            "day": schedules[0].day if schedules else None,
            "due_month": debt.due_month,
        }
        plan = PlanDebt(id=debt.id, kind=debt.kind, owed=0, rate=rate)
        required_now = 0

        if debt.kind == "card":
            account = card_account(db, debt)
            available = c.available_cents if c else 0
            balance = account_balances.get(account.id, 0) if account else 0
            pending_plan = schedules[0].amount_cents if schedules and not paid_now else 0
            owed = card_owed_cents(balance, available, pending_plan)
            if account:
                row["account_id"] = account.id
                row["name"] = account.name
            if schedules:
                amount = schedules[0].amount_cents
                row["plan_monthly_cents"] = amount
                required_now = amount
                plan.roll_cents = amount
                for m in range(start, start + HORIZON_MONTHS):
                    if m == start and paid_now:
                        continue
                    if sched.occurs(schedules[0], sched.month_from_index(m)):
                        plan.required[m] = amount
                if debt.minimum_cents is not None:
                    row["below_minimum"] = amount < debt.minimum_cents
        elif debt.kind == "loan":
            owed = 0
            if schedules:
                s = schedules[0]
                left, first = loan_remaining(s, month, paid_now)
                owed = left * s.amount_cents
                row["installment_cents"] = s.amount_cents
                row["installments_left"] = left
                row["next_month"] = sched.month_from_index(first) if left else None
                required_now = s.amount_cents if sched.occurs(s, month) else 0
                plan.roll_cents = s.amount_cents
                for m in range(first, first + left):
                    plan.required[m] = s.amount_cents
        else:  # personal
            owed = personal_owed(db, user, debt)
            plan.interest_free = rate is None
            if debt.payee_id:
                from ..models import Payee

                payee = db.get(Payee, debt.payee_id)
                row["lender"] = payee.name if payee else None
            if debt.due_month and owed > 0:
                due = max(start, sched.month_index(debt.due_month))
                plan.required[due] = owed
                if c and c.normal_cents is not None:
                    required_now = max(c.normal_cents or 0, c.catch_up_cents or 0)

        plan.owed = float(owed)
        row["owed_cents"] = owed
        row["required_monthly_cents"] = required_now
        row["monthly_interest_cents"] = round(owed * rate) if rate is not None and owed else None
        plans.append(plan)
        rows[debt.id] = row

    simulate(plans, extra, start)

    active = order([p for p in plans if rows[p.id]["owed_cents"] > 0])
    positions = {p.id: i + 1 for i, p in enumerate(active)}
    debts_out = []
    for p in plans:
        row = rows[p.id]
        paid_off = row["owed_cents"] == 0
        row["paid_off"] = paid_off
        row["position"] = positions.get(p.id)
        row["end_month"] = (
            sched.month_from_index(p.end_index) if p.end_index is not None and not paid_off else None
        )
        debts_out.append(DebtOut(**row))
    debts_out.sort(key=lambda d: (d.position is None, d.position or 0))

    ends = [p.end_index for p in active]
    debt_free = (
        sched.month_from_index(max(ends)) if active and all(e is not None for e in ends) else None
    )
    required_total = sum(d.required_monthly_cents for d in debts_out)
    saved = sum(max(0, c.available_cents) for c in cats.values() if c.kind == "savings")
    return DebtsView(
        debts=debts_out,
        total_owed_cents=sum(d.owed_cents for d in debts_out),
        extra_monthly_cents=extra,
        extra_target_debt_id=active[0].id if active else None,
        debt_free_month=debt_free,
        cushion=DebtCushion(
            suggested_cents=min(CUSHION_MAX_CENTS, max(CUSHION_MIN_CENTS, required_total)),
            saved_cents=saved,
        ),
    )


# ---- Writing debts (the only writer of debt schedules, design D4) ----------------------

DEBT_GROUP = "Deudas"


class DebtError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _months_until(target_month: str) -> int:
    return sched.month_index(target_month) - sched.month_index(sched.current_month()) + 1


def _debt_category(db: Session, user: User, name: str):
    from .category_setup import ensure_category, ensure_group

    group, _ = ensure_group(db, user.id, DEBT_GROUP)
    category, _ = ensure_category(db, user.id, group.id, name, "landmark")
    if category.archived:
        category.archived = False
    return category


def _check_free(db: Session, category_id: str, schedules: list[PaymentSchedule]) -> None:
    if debt_for_category(db, category_id) is not None or schedules:
        raise DebtError(409, "debt_exists")


def _schedules_of(db: Session, category_id: str) -> list[PaymentSchedule]:
    return list(
        db.scalars(select(PaymentSchedule).where(PaymentSchedule.category_id == category_id))
    )


def _replace_schedule(db: Session, user: User, category_id: str, schedule: PaymentSchedule | None) -> None:
    from .budget_view import refresh_computed_assignments

    for old in _schedules_of(db, category_id):
        db.delete(old)
    db.flush()
    if schedule is not None:
        schedule.user_id = user.id
        schedule.category_id = category_id
        db.add(schedule)
        db.flush()
    db.expire_all()
    refresh_computed_assignments(db, user, category_id)


def _card_owed(db: Session, user: User, account: Account) -> int:
    from .accounts import balances, payment_category
    from .budget_view import payment_available_by_card

    balance = balances(db, user.id).get(account.id, 0)
    month = sched.current_month()
    available = payment_available_by_card(db, user, month).get(account.id, 0)
    category = payment_category(db, account.id)
    schedules = _schedules_of(db, category.id) if category else []
    pending = 0
    if schedules:
        from .budget_view import build_view

        c = next((c for g in build_view(db, user, month).groups for c in g.categories
                  if c.id == category.id), None)
        if not _occurrence_paid(schedules, month, c.spent_cents if c else 0):
            pending = schedules[0].amount_cents
    return card_owed_cents(balance, available, pending)


def _card_plan(db: Session, user: User, account: Account, rate: float | None,
               plan_monthly_cents: int | None, target_month: str | None) -> int:
    if plan_monthly_cents is not None:
        return plan_monthly_cents
    months = _months_until(target_month or "")
    amount = plan_for_target(_card_owed(db, user, account), rate, months)
    if amount <= 0:
        raise DebtError(422, "invalid_debt")
    return amount


def _plan_schedule(amount: int, day: int | None) -> PaymentSchedule:
    return PaymentSchedule(name="Debt plan", amount_cents=amount, pattern="monthly", day=day,
                           estimated=False)


def _loan_schedule(installment: int, left: int, next_month: str, day: int | None) -> PaymentSchedule:
    return PaymentSchedule(name="Installment", amount_cents=installment, pattern="monthly",
                           count=left, start_month=next_month, day=day, estimated=False)


def _personal_schedule(owed: int, due_month: str | None) -> PaymentSchedule | None:
    if not due_month:
        return None
    return PaymentSchedule(name="Pay back", amount_cents=owed, pattern="once",
                           once_month=due_month, estimated=False)


def create_loan(db: Session, user: User, name: str, installment: int, left: int,
                next_month: str, day: int | None, rate_bp: int | None,
                rate_period: str | None) -> Debt:
    category = _debt_category(db, user, name)
    _check_free(db, category.id, _schedules_of(db, category.id))
    debt = Debt(user_id=user.id, category_id=category.id, kind="loan",
                rate_bp=rate_bp, rate_period=rate_period)
    db.add(debt)
    db.flush()
    _replace_schedule(db, user, category.id, _loan_schedule(installment, left, next_month, day))
    return debt


def create_debt(db: Session, user: User, body) -> Debt:
    from .payees import resolve_payee

    if body.kind == "card":
        account = db.scalar(select(Account).where(Account.id == body.account_id,
                                                  Account.user_id == user.id))
        if account is None:
            raise DebtError(404, "account_not_found")
        from .accounts import payment_category

        category = payment_category(db, account.id)
        if account.type != "credit" or account.archived or category is None:
            raise DebtError(422, "invalid_debt")
        _check_free(db, category.id, _schedules_of(db, category.id))
        rate = monthly_rate(body.rate_bp, body.rate_period)
        amount = _card_plan(db, user, account, rate, body.plan_monthly_cents, body.target_month)
        debt = Debt(user_id=user.id, category_id=category.id, kind="card",
                    rate_bp=body.rate_bp, rate_period=body.rate_period,
                    minimum_cents=body.minimum_cents)
        db.add(debt)
        db.flush()
        _replace_schedule(db, user, category.id, _plan_schedule(amount, account.payment_day))
        return debt
    if body.kind == "loan":
        return create_loan(db, user, body.name, body.installment_cents, body.installments_left,
                           body.next_month, body.day, body.rate_bp, body.rate_period)
    category = _debt_category(db, user, body.name)
    _check_free(db, category.id, _schedules_of(db, category.id))
    payee = resolve_payee(db, user.id, body.lender)
    debt = Debt(user_id=user.id, category_id=category.id, kind="personal",
                rate_bp=body.rate_bp, rate_period=body.rate_period,
                owed_cents=body.owed_cents, due_month=body.due_month,
                payee_id=payee.id if payee else None)
    db.add(debt)
    db.flush()
    _replace_schedule(db, user, category.id, _personal_schedule(body.owed_cents, body.due_month))
    return debt


_KIND_FIELDS = {
    "card": {"plan_monthly_cents", "target_month", "minimum_cents"},
    "loan": {"name", "installment_cents", "installments_left", "next_month", "day"},
    "personal": {"name", "owed_cents", "due_month", "lender"},
}


def update_debt(db: Session, user: User, debt: Debt, body) -> Debt:
    from .payees import resolve_payee

    sent = body.model_fields_set
    common = {"rate_bp", "rate_period"}
    if sent - common - _KIND_FIELDS[debt.kind]:
        raise DebtError(422, "invalid_debt")
    if "rate_bp" in sent:
        debt.rate_bp = body.rate_bp
        debt.rate_period = body.rate_period if body.rate_bp is not None else None
        if debt.rate_bp is not None and debt.rate_period is None:
            raise DebtError(422, "invalid_debt")
    elif "rate_period" in sent and debt.rate_bp is not None and body.rate_period:
        debt.rate_period = body.rate_period
    if "name" in sent and body.name:
        debt.category.name = body.name.strip()
    schedules = _schedules_of(db, debt.category_id)
    current = schedules[0] if schedules else None

    if debt.kind == "card":
        if "minimum_cents" in sent:
            debt.minimum_cents = body.minimum_cents
        if "plan_monthly_cents" in sent or "target_month" in sent:
            account = card_account(db, debt)
            rate = monthly_rate(debt.rate_bp, debt.rate_period)
            amount = _card_plan(db, user, account, rate, body.plan_monthly_cents
                                if "plan_monthly_cents" in sent else None,
                                body.target_month if "target_month" in sent else None)
            _replace_schedule(db, user, debt.category_id,
                              _plan_schedule(amount, account.payment_day if account else None))
    elif debt.kind == "loan":
        if sent & {"installment_cents", "installments_left", "next_month", "day"}:
            installment = body.installment_cents or (current.amount_cents if current else 0)
            left = body.installments_left or (current.count if current else 0)
            next_month = body.next_month or (current.start_month if current else None)
            day = body.day if "day" in sent else (current.day if current else None)
            if not installment or not left or not next_month:
                raise DebtError(422, "invalid_debt")
            _replace_schedule(db, user, debt.category_id,
                              _loan_schedule(installment, left, next_month, day))
    else:
        if "owed_cents" in sent and body.owed_cents:
            debt.owed_cents = body.owed_cents
        if "due_month" in sent:
            debt.due_month = body.due_month
        if "lender" in sent:
            payee = resolve_payee(db, user.id, body.lender)
            debt.payee_id = payee.id if payee else None
        if sent & {"owed_cents", "due_month"}:
            _replace_schedule(db, user, debt.category_id,
                              _personal_schedule(debt.owed_cents or 0, debt.due_month))
    db.flush()
    return debt


def delete_debt(db: Session, user: User, debt: Debt) -> None:
    category_id = debt.category_id
    db.delete(debt)
    db.flush()
    for old in _schedules_of(db, category_id):
        db.delete(old)
    db.flush()


def convert_to_loan(db: Session, user: User, account: Account, body) -> Debt:
    """A loan set up as a card becomes a loan debt (design D6)."""
    from .accounts import payment_category, sync_payment_category
    from .budget_view import build_view, ensure_assignment, materialize_month

    if account.type != "credit" or account.archived:
        raise DebtError(409, "not_convertible")
    old_category = payment_category(db, account.id)
    old_debt = debt_for_category(db, old_category.id) if old_category else None
    if old_debt is not None:
        delete_debt(db, user, old_debt)
    month = sched.current_month()
    available = 0
    if old_category is not None:
        view = build_view(db, user, month)
        available = next((c.available_cents for g in view.groups for c in g.categories
                          if c.id == old_category.id), 0)
    debt = create_loan(db, user, account.name, body.installment_cents, body.installments_left,
                       body.next_month, body.day, body.rate_bp, body.rate_period)
    if old_category is not None and available > 0:
        bm = materialize_month(db, user, month)
        source = ensure_assignment(db, user, bm, old_category.id)
        target = ensure_assignment(db, user, bm, debt.category_id)
        if source is not None and target is not None:
            source.assigned_cents -= available
            target.assigned_cents += available
    account.archived = True
    sync_payment_category(db, account)
    db.flush()
    return debt
