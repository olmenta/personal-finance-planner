"""Coach actions: preview, revision, commit, cancel and undo (spec:
coach-conversation, design D5–D8).

A proposed change is a typed command. Its preview is computed by applying
the command through the same operations as the forms inside a savepoint and
rolling it back, so the before/after values are exactly what a commit would
produce. The revision is a hash of the preview: a commit recomputes it and
refuses when the numbers moved meanwhile. Money itself stays in assignments
and transactions; this table only records the lifecycle.
"""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    BudgetAssignment,
    BudgetMonth,
    Category,
    CategoryGroup,
    CoachAction,
    CoachMessage,
    Debt,
    IncomeSchedule,
    PaymentSchedule,
    Transaction,
    User,
)
from . import budget_moves, budget_view
from . import categories as categories_service
from . import category_matching as matching
from . import debt_ops, income_ops, payment_ops
from .debts import DebtError
from .payment_text import describe
from .categories import CategoryError
from .coach import eur
from .entries import EntryError, create_entry
from .payees import delete_orphan_payees

UNASSIGNED = "To be assigned"


class ActionError(Exception):
    """A lifecycle refusal. `extra` goes into the response detail."""

    def __init__(self, status: int, code: str, extra: dict | None = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.extra = extra or {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def revision_of(preview: dict) -> str:
    return hashlib.sha256(json.dumps(preview, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---- applying a command ----------------------------------------------------------


def _apply(db: Session, user: User, command: dict) -> dict:
    """Apply through the shared operations; returns what undo needs. Raises
    MoveError / EntryError / HTTPException on a refusal."""
    month = command["month"]
    kind = command["kind"]
    if kind == "transaction":
        txn = create_entry(
            db, user,
            amount_cents=command["amount_cents"], kind=command["direction"],
            category_id=command.get("category_id"), account_id=command.get("account_id"),
            payee=command.get("payee"), note=command.get("note"),
            on=datetime.strptime(command["date"], "%Y-%m-%d").date(),
        )
        return {"transaction_id": txn.id, "transaction": _txn_fields(txn)}
    if kind == "category":
        return _create_category(db, user, command)
    if kind in PAYMENT_KINDS:
        return _apply_payment(db, user, command)
    if kind in INCOME_KINDS:
        return _apply_income(db, user, command)
    if kind in DEBT_KINDS:
        return _apply_debt(db, user, command)
    touched = _touched(command)
    before = _assigned(db, user, month, touched)
    if kind == "assignment":
        budget_moves.set_assignment(db, user, month, command["category_id"], command["amount_cents"])
    elif kind == "assignments":
        for item in command["items"]:
            budget_moves.set_assignment(db, user, month, item["category_id"], item["amount_cents"])
    elif kind == "moves":
        for move in command["moves"]:
            budget_moves.apply_move(
                db, user, month, move["from_category_id"], move["to_category_id"], move["amount_cents"]
            )
    else:
        raise ValueError(f"unknown action kind {kind!r}")
    after = _assigned(db, user, month, touched)
    return {
        "assignments": [
            {"category_id": cid, "before_cents": before[cid], "after_cents": after[cid]} for cid in touched
        ]
    }


def _touched(command: dict) -> list[str]:
    if command["kind"] == "assignment":
        return [command["category_id"]]
    if command["kind"] == "assignments":
        return [item["category_id"] for item in command["items"]]
    if command["kind"] in ("category", *INCOME_KINDS, *DEBT_KINDS):
        return []
    if command["kind"] == "moves":
        ids: list[str] = []
        for move in command["moves"]:
            for cid in (move["from_category_id"], move["to_category_id"]):
                if cid and cid not in ids:
                    ids.append(cid)
        return ids
    return [command["category_id"]] if command.get("category_id") else []


def _assignment_rows(db: Session, user: User, month: str, ids: list[str]) -> dict[str, BudgetAssignment]:
    bm = budget_view.materialize_month(db, user, month)
    rows = db.scalars(
        select(BudgetAssignment).where(
            BudgetAssignment.budget_month_id == bm.id, BudgetAssignment.category_id.in_(ids)
        )
    )
    return {row.category_id: row for row in rows}


def _assigned(db: Session, user: User, month: str, ids: list[str]) -> dict[str, int]:
    rows = _assignment_rows(db, user, month, ids)
    return {cid: rows[cid].assigned_cents if cid in rows else 0 for cid in ids}


def _txn_fields(txn: Transaction) -> dict:
    return {
        "amount_cents": txn.amount_cents, "category_id": txn.category_id,
        "account_id": txn.account_id, "payee_id": txn.payee_id,
        "date": txn.date.isoformat(), "description": txn.description,
    }


def _refusal(error: Exception) -> dict:
    """The refusal as the forms report it: code, status and extra fields."""
    if isinstance(error, budget_moves.MoveError):
        return {"code": error.code, "status": error.status, **error.extra}
    if isinstance(error, (EntryError, CategoryError, payment_ops.PaymentError, income_ops.IncomeError, DebtError)):
        return {"code": error.code, "status": error.status}
    detail = getattr(error, "detail", None)
    status = getattr(error, "status_code", 422)
    if isinstance(detail, dict) and "code" in detail:
        return {"code": detail["code"], "status": status}
    return {"code": "invalid_action", "status": 422}


REFUSALS = (
    budget_moves.MoveError, EntryError, HTTPException, CategoryError, payment_ops.PaymentError,
    income_ops.IncomeError, DebtError,
)


# ---- payments (coach-payments-setup design D2–D4) -----------------------------------

PAYMENT_KINDS = ("payment", "payment_update", "payment_delete")


def _apply_payment(db: Session, user: User, command: dict) -> dict:
    kind = command["kind"]
    if kind == "payment":
        schedule = payment_ops.create_payment(db, user, command["category_id"], command["body"])
        return {"schedule_id": schedule.id, "after": payment_ops.fields_of(schedule)}
    # What it really was right before (the editor may have changed it since
    # the proposal): that's what undo restores.
    before = payment_ops.fields_of(payment_ops.schedule_or_404(db, user, command["schedule_id"]))
    if kind == "payment_update":
        schedule = payment_ops.update_payment(db, user, command["schedule_id"], command["changes"])
        return {"schedule_id": schedule.id, "before": before, "after": payment_ops.fields_of(schedule)}
    payment_ops.delete_payment(db, user, command["schedule_id"])
    return {"schedule_id": command["schedule_id"], "before": before}


def _current_fields(db: Session, user: User, command: dict) -> dict | None:
    """The payment as it is now (None for a new one, or when it's gone)."""
    if command["kind"] == "payment":
        return None
    schedule = db.scalar(select(PaymentSchedule).where(
        PaymentSchedule.id == command["schedule_id"], PaymentSchedule.user_id == user.id))
    return payment_ops.fields_of(schedule) if schedule else command.get("before")


def _after_fields(command: dict, current: dict | None = None) -> dict | None:
    if command["kind"] == "payment":
        return payment_ops.merged_fields({}, command["body"])
    if command["kind"] == "payment_update":
        return payment_ops.merged_fields(current or command["before"], command["changes"])
    return None


def _next_due(db: Session, user: User, category_id: str, month: str) -> str | None:
    """The first month from `month` in which the category pays something."""
    from . import schedules as sched

    schedules = sched.schedules_by_category(db, user).get(category_id, [])
    start = sched.month_index(month)
    if not schedules:
        return None
    for index in range(start, sched.horizon_end(schedules, start) + 1):
        if sched.payments_in(schedules, sched.month_from_index(index)) > 0:
            return sched.month_from_index(index)
    return None


def _payment_preview(before_view, after_view, command: dict, next_due: str | None, current: dict | None) -> dict:
    cid = command["category_id"]
    before = budget_moves.find_category(before_view, cid)
    after = budget_moves.find_category(after_view, cid) if after_view is not None else before
    after_fields = _after_fields(command, current)
    return {
        "title": title(command, current),
        "payment": {
            "name": (after_fields or current or {}).get("name"),
            "sentence_before": describe(current) if current else None,
            "sentence_after": describe(after_fields) if after_fields else None,
            "next_due_month": next_due,
            "estimated": bool((after_fields or {}).get("estimated")),
            "category_id": cid,
        },
        "amounts": {
            "normal_before_cents": (before.normal_cents or 0) if before else 0,
            "normal_after_cents": (after.normal_cents or 0) if after else 0,
            "catch_up_before_cents": (before.catch_up_cents or 0) if before else 0,
            "catch_up_after_cents": (after.catch_up_cents or 0) if after else 0,
        },
    }


# ---- expected income (coach-income-setup design D2–D4) ---------------------------------

INCOME_KINDS = ("income", "income_update", "income_delete", "income_link")


def _apply_income(db: Session, user: User, command: dict) -> dict:
    kind = command["kind"]
    if kind == "income":
        schedule = income_ops.create_income(db, user, command["body"])
        return {"schedule_id": schedule.id, "after": income_ops.fields_of(schedule)}
    if kind == "income_link":
        txn = income_ops.inflow_or_404(db, user, command["transaction_id"])
        schedule = income_ops.schedule_or_404(db, user, command["schedule_id"])
        before = {"txn_payee": txn.payee_id, "schedule_payee": schedule.payee_id}
        income_ops.link_income(db, user, command["transaction_id"], command["schedule_id"])
        return {"transaction_id": txn.id, "schedule_id": schedule.id, "before": before,
                "after": {"txn_payee": txn.payee_id, "schedule_payee": schedule.payee_id}}
    before = income_ops.fields_of(income_ops.schedule_or_404(db, user, command["schedule_id"]))
    if kind == "income_update":
        schedule = income_ops.update_income(db, user, command["schedule_id"], command["changes"])
        return {"schedule_id": schedule.id, "before": before, "after": income_ops.fields_of(schedule)}
    income_ops.delete_income(db, user, command["schedule_id"])
    return {"schedule_id": command["schedule_id"], "before": before}


def income_sentence(fields: dict) -> str:
    """"2.100,00 € every month, day 28, from Acme"."""
    text = describe(fields)
    return f"{text}, from {fields['payer']}" if fields.get("payer") else text


def _current_income(db: Session, user: User, command: dict) -> dict | None:
    if command["kind"] not in ("income_update", "income_delete"):
        return None
    schedule = db.scalar(select(IncomeSchedule).where(
        IncomeSchedule.id == command["schedule_id"], IncomeSchedule.user_id == user.id))
    return income_ops.fields_of(schedule) if schedule else command.get("before")


def _income_after(command: dict, current: dict | None) -> dict | None:
    if command["kind"] == "income":
        return income_ops.merged_fields({}, command["body"])
    if command["kind"] == "income_update":
        return income_ops.merged_fields(current or command["before"], command["changes"])
    return None


def _plan_values(db: Session, user: User, month: str, link: dict | None) -> dict:
    """Expected income this month and over 12 months, the year's coverage,
    and (for a link) the occurrence's state."""
    from .income import month_income, user_schedules, yearly_cents
    from .projection import summary

    view = month_income(db, user, month)
    plan = summary(db, user, month)
    values = {
        "month_expected_cents": view.expected_cents,
        "year_expected_cents": sum(yearly_cents(s) for s in user_schedules(db, user)),
        "income_known": plan.income_known,
        "gap_cents": plan.gap_cents,
    }
    if link:
        occ = next((o for o in view.occurrences if o.schedule_id == link["schedule_id"]), None)
        values["occurrence"] = {"name": occ.name, "status": occ.status, "received_cents": occ.received_cents} if occ else None
        values["unplanned"] = any(u.transaction_id == link["transaction_id"] for u in view.unplanned)
    return values


def _income_preview(db: Session, user: User, command: dict) -> dict:
    month = command["month"]
    current = _current_income(db, user, command)
    link = command if command["kind"] == "income_link" else None
    before = _plan_values(db, user, month, link)
    after, error = None, None
    savepoint = db.begin_nested()
    try:
        _apply_income(db, user, command)
        after = _plan_values(db, user, month, link)
    except REFUSALS as refusal:
        error = _refusal(refusal)
    finally:
        savepoint.rollback()
    after = after or before
    after_fields = _income_after(command, current)
    result = {
        "kind": command["kind"],
        "month": month,
        "title": title(command, current),
        "income": {
            "sentence_before": income_sentence(current) if current else None,
            "sentence_after": income_sentence(after_fields) if after_fields else None,
            "estimated": bool((after_fields or {}).get("estimated")),
        },
        "plan": {
            "month_expected_before_cents": before["month_expected_cents"],
            "month_expected_after_cents": after["month_expected_cents"],
            "year_expected_before_cents": before["year_expected_cents"],
            "year_expected_after_cents": after["year_expected_cents"],
            "income_known_before": before["income_known"],
            "income_known_after": after["income_known"],
            "gap_before_cents": before["gap_cents"],
            "gap_after_cents": after["gap_cents"],
        },
        "categories": [],
        "accounts_unchanged": True,
        # Expected income plans; only money that arrives is assigned.
        "to_be_assigned_unchanged": True,
        "error": error,
    }
    if link:
        result["link"] = {"amount_cents": command["amount_cents"],
                          "occurrence_before": before.get("occurrence"), "occurrence_after": after.get("occurrence"),
                          "unplanned_before": before.get("unplanned"), "unplanned_after": after.get("unplanned")}
    return result


# ---- debts (coach-debts-setup design D2–D4) -------------------------------------------

DEBT_KINDS = ("debt", "debt_update", "debt_delete", "debt_extra", "debt_convert")


def _apply_debt(db: Session, user: User, command: dict) -> dict:
    kind = command["kind"]
    if kind == "debt":
        debt = debt_ops.create(db, user, command["body"])
        return {"debt_id": debt.id, "category_id": debt.category_id, "after": debt_ops.fields_of(db, user, debt)}
    if kind == "debt_extra":
        previous = debt_ops.set_extra(db, user, command["extra_cents"])
        return {"extra_before": previous, "extra_after": command["extra_cents"]}
    if kind == "debt_convert":
        debt = debt_ops.convert(db, user, command["account_id"], command["body"])
        return {"debt_id": debt.id, "category_id": debt.category_id}
    debt = debt_ops.debt_or_404(db, user, command["debt_id"])
    before = debt_ops.fields_of(db, user, debt)
    category_id = debt.category_id
    if kind == "debt_update":
        debt = debt_ops.update(db, user, command["debt_id"], command["changes"])
        return {"debt_id": debt.id, "category_id": category_id, "before": before,
                "after": debt_ops.fields_of(db, user, debt)}
    debt_ops.delete(db, user, command["debt_id"])
    return {"debt_id": command["debt_id"], "category_id": category_id, "before": before}


def debt_text(row) -> str:
    """A debt's plan in words: "200,00 € a month · done in January 2027"."""
    from .payment_text import month_label

    if row is None:
        return "no plan"
    if row.kind == "card":
        text = f"{eur(row.plan_monthly_cents)} a month" if row.plan_monthly_cents else "no plan"
    elif row.kind == "loan":
        text = (f"{eur(row.installment_cents or 0)} × {row.installments_left or 0} from "
                f"{month_label(row.next_month)}" + (f", day {row.day}" if row.day else ""))
    else:
        text = eur(row.owed_cents) + (f", due {month_label(row.due_month)}" if row.due_month else ", no date")
        if row.lender:
            text += f", to {row.lender}"
    if row.kind != "personal" and row.end_month:
        text += f" · done in {month_label(row.end_month)}"
    return text


def _debts_snapshot(db: Session, user: User, debt_id: str | None, category_id: str | None, month: str) -> dict:
    from .debts import build_debts_view

    view = build_debts_view(db, user)
    budget = budget_view.build_view(db, user, month)
    row = next((d for d in view.debts if d.id == debt_id), None) if debt_id else None
    target = next((d.name for d in view.debts if d.id == view.extra_target_debt_id), None)
    category = budget_moves.find_category(budget, category_id) if category_id else None
    return {
        "total_owed_cents": view.total_owed_cents,
        "debt_free_month": view.debt_free_month,
        "extra_monthly_cents": view.extra_monthly_cents,
        "extra_target": target,
        "cushion": view.cushion.model_dump(),
        "to_be_assigned_cents": budget.to_be_assigned_cents,
        "row": {
            "name": row.name, "kind": row.kind, "position": row.position, "end_month": row.end_month,
            "required_monthly_cents": row.required_monthly_cents, "below_minimum": row.below_minimum,
            "monthly_interest_cents": row.monthly_interest_cents, "text": debt_text(row),
        } if row else None,
        "category": {"category_id": category.id, "name": category.name, "assigned_cents": category.assigned_cents,
                     "available_cents": category.available_cents} if category else None,
    }


_RESTORE_FIELDS = {
    "card": ("plan_monthly_cents", "minimum_cents"),
    "loan": ("name", "installment_cents", "installments_left", "next_month", "day"),
    "personal": ("name", "owed_cents", "due_month", "lender"),
}


def _debt_restore(before: dict) -> dict:
    """The update that puts a debt back to `before` (its recorded fields)."""
    changes = {k: before.get(k) for k in _RESTORE_FIELDS[before["kind"]]}
    changes["rate_bp"] = before.get("rate_bp")
    changes["rate_period"] = before.get("rate_period")
    return changes


def _debt_preview(db: Session, user: User, command: dict) -> dict:
    month = command["month"]
    debt_id = command.get("debt_id")
    category_id = command.get("category_id")
    before = _debts_snapshot(db, user, debt_id, category_id, month)
    after, error = None, None
    savepoint = db.begin_nested()
    try:
        result = _apply_debt(db, user, command)
        after = _debts_snapshot(db, user, result.get("debt_id") if command["kind"] != "debt_delete" else None,
                                result.get("category_id") or category_id, month)
    except REFUSALS as refusal:
        error = _refusal(refusal)
    finally:
        savepoint.rollback()
    after = after or before
    b_cat, a_cat = before["category"], after["category"]
    categories = []
    if a_cat or b_cat:
        cat = a_cat or b_cat
        categories.append({
            # A category the dry run creates gets a new id each time: leave it
            # out, or every revision would differ and the commit go stale.
            "category_id": b_cat["category_id"] if b_cat else None, "name": cat["name"],
            "assigned_before_cents": b_cat["assigned_cents"] if b_cat else 0,
            "assigned_after_cents": a_cat["assigned_cents"] if a_cat else (b_cat or {}).get("assigned_cents", 0),
            "available_before_cents": b_cat["available_cents"] if b_cat else 0,
            "available_after_cents": a_cat["available_cents"] if a_cat else (b_cat or {}).get("available_cents", 0),
        })
    cushion = after["cushion"]
    return {
        "kind": command["kind"],
        "month": month,
        "title": title(command),
        "debt": {
            "before": before["row"], "after": after["row"] if command["kind"] != "debt_delete" else None,
            "debt_free_before": before["debt_free_month"], "debt_free_after": after["debt_free_month"],
            "total_owed_before_cents": before["total_owed_cents"], "total_owed_after_cents": after["total_owed_cents"],
            "extra_before_cents": before["extra_monthly_cents"], "extra_after_cents": after["extra_monthly_cents"],
            "extra_target": after["extra_target"],
            "cushion_note": (command["kind"] == "debt_extra" and after["extra_monthly_cents"] > 0
                             and cushion["saved_cents"] < cushion["suggested_cents"]),
            "cushion_suggested_cents": cushion["suggested_cents"],
        },
        "categories": categories,
        "to_be_assigned_before_cents": before["to_be_assigned_cents"],
        "to_be_assigned_after_cents": after["to_be_assigned_cents"],
        "accounts_unchanged": True,
        "error": error,
    }


# ---- creating a category (coach-budget-setup design D2) -----------------------------


def _create_category(db: Session, user: User, command: dict) -> dict:
    """Create the category in the chosen group (or a new group, reusing one
    with the same name). The choice comes in `command["choice"]`."""
    choice = command.get("choice") or {}
    created_group = False
    if choice.get("new_group_name"):
        same = [m for m in matching.similar_groups(db, user, choice["new_group_name"]) if m.reason == "same_name"]
        if same:
            group_id = same[0].id
        else:
            group_id = categories_service.create_group(db, user.id, choice["new_group_name"]).id
            created_group = True
    else:
        group_id = choice.get("group_id") or command.get("suggested_group_id")
        if group_id not in {g.id for g in matching.user_groups(db, user)}:
            raise CategoryError(404, "group_not_found")
    category = categories_service.create_category(db, user.id, group_id, command["name"])
    return {"category_id": category.id, "group_id": group_id, "created_group": created_group}


def _category_in_use(db: Session, category_id: str) -> bool:
    from ..models import PaymentSchedule

    used = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id))
    assigned = db.scalar(select(func.count()).select_from(BudgetAssignment).where(
        BudgetAssignment.category_id == category_id, BudgetAssignment.assigned_cents != 0))
    scheduled = db.scalar(select(func.count()).select_from(PaymentSchedule).where(
        PaymentSchedule.category_id == category_id))
    return bool(used or assigned or scheduled)


def _category_preview(db: Session, user: User, command: dict) -> dict:
    groups = matching.user_groups(db, user)
    by_id = {c.id: c for c in matching.spendable_categories(db, user)}
    # The string matches are recomputed on every preview, so a similar
    # category created meanwhile makes the choice stale; the model's
    # meaning-based hints are kept from the proposal.
    options = [{"id": m.id, "reason": m.reason} for m in matching.similar_categories(db, user, command["name"])]
    options += [h for h in command["similar"] if all(o["id"] != h["id"] for o in options)]
    similar = [
        {"id": o["id"], "name": by_id[o["id"]].name, "group_id": by_id[o["id"]].group_id,
         "group_name": by_id[o["id"]].group.name, "reason": o["reason"]}
        for o in options if o["id"] in by_id
    ][:matching.MAX_MATCHES]
    suggested = command.get("suggested_group_id")
    if suggested not in {g.id for g in groups}:
        fallback = matching.suggest_group(db, user, command["name"])
        suggested = fallback.id if fallback else None
    follow = command.get("for")
    # No money values: a choice only goes stale when the categories or
    # groups it offers change.
    return {
        "kind": "category",
        "month": command["month"],
        "title": title(command),
        "name": command["name"],
        "similar": similar,
        "groups": [{"id": g.id, "name": g.name} for g in groups],
        "suggested_group_id": suggested,
        "follow_up_title": title({**follow, "category_name": command["name"]}) if follow else None,
        "categories": [],
        "accounts_unchanged": True,
        "error": None,
    }


def follow_up(db: Session, user: User, action: CoachAction, category_id: str) -> CoachAction | None:
    """Propose the step the category was for, with the chosen category. A
    refusal is recorded on the category action instead of failing it."""
    follow = action.command.get("for")
    if not follow:
        return None
    name = db.scalar(select(Category.name).where(Category.id == category_id, Category.user_id == user.id))
    command = {**follow, "category_id": category_id, "category_name": name}
    try:
        new = propose(db, user, command)
    except ActionError as error:
        action.result = {**(action.result or {}), "follow_up_error": error.code}
        return None
    new.message_id = action.message_id
    action.result = {**(action.result or {}), "follow_up_id": new.id}
    if action.message_id:
        message = db.get(CoachMessage, action.message_id)
        if message is not None:
            from .coach_widgets import envelope

            message.widgets = [*(message.widgets or []), envelope("action_preview", {"action_id": new.id}, None)]
    db.flush()
    return new


def resolve_choice(db: Session, user: User, action_id: str, category_id: str) -> tuple[CoachAction, CoachAction | None]:
    """"Use X" on a category choice: no category is created; the pending step
    is proposed with X."""
    action = get_action(db, user, action_id, lock=True)
    if action.kind != "category":
        raise ActionError(422, "not_a_category_choice")
    if action.status == "resolved" and (action.result or {}).get("category_id") == category_id:
        follow_id = (action.result or {}).get("follow_up_id")
        return action, get_action(db, user, follow_id) if follow_id else None
    if action.status != "proposed":
        raise ActionError(409, "action_closed")
    if category_id not in {c.id for c in matching.spendable_categories(db, user)}:
        raise ActionError(404, "category_not_found")
    action.status = "resolved"
    action.result = {"category_id": category_id, "resolved": True}
    action.applied_at = _now()
    db.flush()
    return action, follow_up(db, user, action, category_id)


# ---- preview ---------------------------------------------------------------------


def _category_rows(view, ids: list[str]) -> dict[str, dict]:
    rows = {}
    for cid in ids:
        c = budget_moves.find_category(view, cid)
        if c is not None:
            rows[cid] = {"name": c.name, "assigned_cents": c.assigned_cents,
                         "available_cents": c.available_cents}
    return rows


def preview(db: Session, user: User, command: dict) -> dict:
    """Before/after values of `command`, computed by a dry run. A refusal is
    part of the preview (`error`), so the coach can explain it."""
    if command["kind"] == "category":
        return _category_preview(db, user, command)
    if command["kind"] in INCOME_KINDS:
        return _income_preview(db, user, command)
    if command["kind"] in DEBT_KINDS:
        return _debt_preview(db, user, command)
    month = command["month"]
    ids = _touched(command)
    before_view = budget_view.build_view(db, user, month)
    before = _category_rows(before_view, ids)
    error = None
    after_view = None
    next_due = None
    savepoint = db.begin_nested()
    try:
        _apply(db, user, command)
        after_view = budget_view.build_view(db, user, month)
        if command["kind"] in PAYMENT_KINDS:
            next_due = _next_due(db, user, command["category_id"], month)
    except REFUSALS as refusal:
        error = _refusal(refusal)
    finally:
        savepoint.rollback()
    after = _category_rows(after_view, ids) if after_view is not None else before
    categories = [
        {
            "category_id": cid,
            "name": before[cid]["name"] if cid in before else command.get("category_name", ""),
            "assigned_before_cents": before.get(cid, {}).get("assigned_cents", 0),
            "assigned_after_cents": after.get(cid, {}).get("assigned_cents", 0),
            "available_before_cents": before.get(cid, {}).get("available_cents", 0),
            "available_after_cents": after.get(cid, {}).get("available_cents", 0),
        }
        for cid in ids
    ]
    result = {
        "kind": command["kind"],
        "month": month,
        "title": title(command),
        "categories": categories,
        "to_be_assigned_before_cents": before_view.to_be_assigned_cents,
        "to_be_assigned_after_cents": (
            after_view.to_be_assigned_cents if after_view is not None else before_view.to_be_assigned_cents
        ),
        # Budget changes only give money a different job; a transaction moves it.
        "accounts_unchanged": command["kind"] != "transaction",
        "error": error,
    }
    if command["kind"] in PAYMENT_KINDS:
        current = _current_fields(db, user, command)
        result.update(_payment_preview(before_view, after_view, command, next_due, current))
    if command["kind"] == "transaction":
        result["transaction"] = {
            key: command.get(key)
            for key in ("amount_cents", "direction", "category_name", "payee", "date", "account_name", "note")
        }
    return result


def title(command: dict, current: dict | None = None) -> str:
    """Deterministic one-line description (English placeholder until next-intl)."""
    if command["kind"] == "transaction":
        verb = "Record income of" if command["direction"] == "income" else "Record"
        where = f" at {command['payee']}" if command.get("payee") else ""
        into = f" in {command['category_name']}" if command.get("category_name") else ""
        return f"{verb} {eur(command['amount_cents'])}{where}{into}"
    if command["kind"] == "assignment":
        return f"Set {command['category_name']} to {eur(command['amount_cents'])}"
    if command["kind"] == "assignments":
        items = command["items"]
        if len(items) == 1:
            return f"Set {items[0]['category_name']} to {eur(items[0]['amount_cents'])}"
        listed = ", ".join(f"{i['category_name']} {eur(i['amount_cents'])}" for i in items)
        return f"Set {len(items)} categories: {listed}"
    if command["kind"] == "category":
        return f"Create category {command['name']}"
    if command["kind"] == "payment":
        return f"Add payment: {command['body']['name']}, {describe(_after_fields(command))}"
    if command["kind"] == "payment_update":
        now = current or command["before"]
        return f"Change payment: {now['name']}, {describe(_after_fields(command, now))}"
    if command["kind"] == "payment_delete":
        now = current or command["before"]
        return f"Remove payment: {now['name']} ({describe(now)})"
    if command["kind"] == "income":
        return f"Add income: {command['body']['name']}, {income_sentence(_income_after(command, None))}"
    if command["kind"] == "income_update":
        now = current or command["before"]
        return f"Change income: {now['name']}, {income_sentence(_income_after(command, now))}"
    if command["kind"] == "income_delete":
        now = current or command["before"]
        return f"Remove income: {now['name']} ({income_sentence(now)})"
    if command["kind"] == "income_link":
        return f"Link {eur(command['amount_cents'])} to {command['schedule_name']}"
    if command["kind"] == "debt":
        return f"Add debt: {command['label']}"
    if command["kind"] == "debt_update":
        return f"Change debt: {command['label']}"
    if command["kind"] == "debt_delete":
        return f"Remove the plan of {command['label']}"
    if command["kind"] == "debt_extra":
        return f"Pay {eur(command['extra_cents'])} extra a month on debts"
    if command["kind"] == "debt_convert":
        return f"Turn {command['label']} into a loan"
    moves = command["moves"]
    if len(moves) == 1:
        m = moves[0]
        return f"Move {eur(m['amount_cents'])} from {m.get('from_name') or UNASSIGNED} to {m['to_name']}"
    total = sum(m["amount_cents"] for m in moves)
    return f"Move {eur(total)} to {', '.join(m['to_name'] for m in moves)}"


def propose(db: Session, user: User, command: dict, message_id: str | None = None) -> CoachAction:
    """Store a proposed action with its preview. Raises ActionError when the
    dry run refuses it (the coach explains instead of offering it)."""
    shown = preview(db, user, command)
    if shown["error"]:
        raise ActionError(shown["error"]["status"], shown["error"]["code"], shown["error"])
    action = CoachAction(
        user_id=user.id, message_id=message_id, kind=command["kind"], command=command,
        preview=shown, revision=revision_of(shown), status="proposed",
    )
    db.add(action)
    db.flush()
    return action


# ---- lifecycle -------------------------------------------------------------------


def get_action(db: Session, user: User, action_id: str, *, lock: bool = False) -> CoachAction:
    query = select(CoachAction).where(CoachAction.id == action_id, CoachAction.user_id == user.id)
    if lock:
        query = query.with_for_update()
    action = db.scalar(query)
    if action is None:
        raise ActionError(404, "action_not_found")
    return action


def _lock_month(db: Session, user: User, month: str) -> None:
    """The shared mutation boundary (design D7): concurrent commits and undos
    on the same month serialize on its row."""
    budget_view.materialize_month(db, user, month)
    db.execute(
        select(BudgetMonth.id)
        .where(BudgetMonth.user_id == user.id, BudgetMonth.month == month)
        .with_for_update()
    )


def _replace_in_message(db: Session, old: CoachAction, new: CoachAction) -> None:
    """Point the message's preview widget at the replacement action."""
    if not old.message_id:
        return
    message = db.get(CoachMessage, old.message_id)
    if message is None:
        return
    widgets = []
    for widget in message.widgets or []:
        data = widget.get("data") or {}
        if widget.get("type") in ("action_preview", "category_choice") and data.get("action_id") == old.id:
            widget = {**widget, "data": {**data, "action_id": new.id}}
        widgets.append(widget)
    message.widgets = widgets
    new.message_id = old.message_id


def replace(db: Session, user: User, old: CoachAction, command: dict) -> CoachAction:
    """A new proposal in place of a proposed one (Edit, or a stale review)."""
    new = propose(db, user, command)
    _replace_in_message(db, old, new)
    if old.status == "proposed":
        old.status = "cancelled"
    db.flush()
    return new


def commit(
    db: Session, user: User, action_id: str, revision: str, idempotency_key: str, choice: dict | None = None
) -> CoachAction:
    """Apply a proposed action once. A category action also takes the user's
    group choice (`group_id` or `new_group_name`)."""
    action = get_action(db, user, action_id, lock=True)
    if action.status == "applied":
        if action.idempotency_key == idempotency_key:
            return action  # a retry of the same confirm: the recorded result
        raise ActionError(409, "already_applied")
    if action.status in ("cancelled", "undone", "resolved"):
        raise ActionError(409, "action_closed")
    _lock_month(db, user, action.command["month"])
    fresh = preview(db, user, action.command)
    if fresh["error"]:
        action.status = "stale"
        raise ActionError(fresh["error"]["status"], fresh["error"]["code"], fresh["error"])
    if action.status == "stale" or revision != action.revision or revision_of(fresh) != action.revision:
        action.status = "stale"
        new = CoachAction(
            user_id=user.id, message_id=None, kind=action.kind, command=action.command,
            preview=fresh, revision=revision_of(fresh), status="proposed",
        )
        db.add(new)
        db.flush()
        _replace_in_message(db, action, new)
        raise ActionError(409, "action_stale", {"action_id": new.id})
    command = {**action.command, "choice": choice} if action.kind == "category" else action.command
    savepoint = db.begin_nested()
    try:
        result = _apply(db, user, command)
    except REFUSALS as refusal:
        savepoint.rollback()
        detail = _refusal(refusal)
        raise ActionError(detail["status"], detail["code"], detail) from refusal
    savepoint.commit()
    action.status = "applied"
    action.idempotency_key = idempotency_key
    action.result = result
    action.applied_at = _now()
    db.flush()
    if action.kind == "category":
        follow_up(db, user, action, result["category_id"])
    return action


def cancel(db: Session, user: User, action_id: str) -> CoachAction:
    action = get_action(db, user, action_id, lock=True)
    if action.status == "cancelled":
        return action
    if action.status not in ("proposed", "stale"):
        raise ActionError(409, "action_closed")
    action.status = "cancelled"
    db.flush()
    return action


def can_undo(db: Session, user: User, action: CoachAction) -> bool:
    """Everything the action touched still holds the values it left."""
    if action.status != "applied" or not action.result:
        return False
    if action.kind == "transaction":
        txn = db.scalar(
            select(Transaction).where(
                Transaction.id == action.result["transaction_id"], Transaction.user_id == user.id
            )
        )
        return txn is not None and _txn_fields(txn) == action.result["transaction"]
    if action.kind == "category":
        category = db.scalar(select(Category).where(
            Category.id == action.result["category_id"], Category.user_id == user.id))
        return category is not None and not category.archived and not _category_in_use(db, category.id)
    if action.kind in ("payment", "payment_update"):
        schedule = db.scalar(select(PaymentSchedule).where(
            PaymentSchedule.id == action.result["schedule_id"], PaymentSchedule.user_id == user.id))
        return schedule is not None and payment_ops.fields_of(schedule) == action.result["after"]
    if action.kind in ("income", "income_update"):
        schedule = db.scalar(select(IncomeSchedule).where(
            IncomeSchedule.id == action.result["schedule_id"], IncomeSchedule.user_id == user.id))
        return schedule is not None and income_ops.fields_of(schedule) == action.result["after"]
    if action.kind == "income_delete":
        schedules = db.scalars(select(IncomeSchedule).where(IncomeSchedule.user_id == user.id))
        return all(income_ops.fields_of(s) != action.result["before"] for s in schedules)
    if action.kind == "income_link":
        txn = db.get(Transaction, action.result["transaction_id"])
        schedule = db.get(IncomeSchedule, action.result["schedule_id"])
        after = action.result["after"]
        return (txn is not None and schedule is not None and txn.payee_id == after["txn_payee"]
                and schedule.payee_id == after["schedule_payee"])
    if action.kind in ("debt", "debt_update"):
        debt = db.scalar(select(Debt).where(Debt.id == action.result["debt_id"], Debt.user_id == user.id))
        return debt is not None and debt_ops.fields_of(db, user, debt) == action.result["after"]
    if action.kind == "debt_delete":
        from .debts import debt_for_category

        return debt_for_category(db, action.result["category_id"]) is None
    if action.kind == "debt_extra":
        from .debts import settings as debt_settings

        return debt_settings(db, user).extra_monthly_cents == action.result["extra_after"]
    if action.kind == "debt_convert":
        return False
    if action.kind == "payment_delete":
        category = db.scalar(select(Category).where(
            Category.id == action.command["category_id"], Category.user_id == user.id))
        if category is None or category.archived:
            return False
        same = [s for s in category.schedules if payment_ops.fields_of(s) == action.result["before"]]
        return not same
    items = action.result["assignments"]
    current = _assigned(db, user, action.command["month"], [i["category_id"] for i in items])
    return all(current[i["category_id"]] == i["after_cents"] for i in items)


def undo(db: Session, user: User, action_id: str) -> CoachAction:
    action = get_action(db, user, action_id, lock=True)
    if action.status == "undone":
        return action
    _lock_month(db, user, action.command["month"])
    if not can_undo(db, user, action):
        raise ActionError(409, "undo_not_possible")
    if action.kind == "transaction":
        txn = db.get(Transaction, action.result["transaction_id"])
        payee_id = txn.payee_id
        db.delete(txn)
        db.flush()
        if payee_id:
            delete_orphan_payees(db, user.id, {payee_id})
    elif action.kind in DEBT_KINDS:
        try:
            if action.kind == "debt":
                debt_ops.delete(db, user, action.result["debt_id"])
            elif action.kind == "debt_update":
                debt_ops.update(db, user, action.result["debt_id"], _debt_restore(action.result["before"]))
            elif action.kind == "debt_delete":
                recreated = debt_ops.create(db, user, action.result["before"])
                action.result = {**action.result, "recreated_id": recreated.id}
            else:
                debt_ops.set_extra(db, user, action.result["extra_before"])
        except DebtError as error:
            raise ActionError(409, "undo_not_possible") from error
    elif action.kind in INCOME_KINDS:
        try:
            if action.kind == "income":
                income_ops.delete_income(db, user, action.result["schedule_id"])
            elif action.kind == "income_update":
                income_ops.update_income(db, user, action.result["schedule_id"], action.result["before"])
            elif action.kind == "income_delete":
                body = {k: v for k, v in action.result["before"].items() if v is not None}
                recreated = income_ops.create_income(db, user, body)
                action.result = {**action.result, "recreated_id": recreated.id}
            else:
                txn = db.get(Transaction, action.result["transaction_id"])
                schedule = db.get(IncomeSchedule, action.result["schedule_id"])
                txn.payee_id = action.result["before"]["txn_payee"]
                schedule.payee_id = action.result["before"]["schedule_payee"]
                db.flush()
        except income_ops.IncomeError as error:
            raise ActionError(409, "undo_not_possible") from error
    elif action.kind in PAYMENT_KINDS:
        try:
            if action.kind == "payment":
                payment_ops.delete_payment(db, user, action.result["schedule_id"])
            elif action.kind == "payment_update":
                payment_ops.update_payment(db, user, action.result["schedule_id"], action.result["before"])
            else:
                body = {k: v for k, v in action.result["before"].items() if v is not None}
                recreated = payment_ops.create_payment(db, user, action.command["category_id"], body)
                action.result = {**action.result, "recreated_id": recreated.id}
        except payment_ops.PaymentError as error:
            raise ActionError(409, "undo_not_possible") from error
    elif action.kind == "category":
        # Nothing references an unused category (checked above): remove it,
        # and the group this action created when it's left empty.
        category = db.get(Category, action.result["category_id"])
        for row in db.scalars(select(BudgetAssignment).where(BudgetAssignment.category_id == category.id)):
            db.delete(row)
        db.delete(category)
        db.flush()
        if action.result.get("created_group"):
            group = db.get(CategoryGroup, action.result["group_id"])
            left = db.scalar(select(func.count()).select_from(Category).where(Category.group_id == group.id))
            if group is not None and not left:
                db.delete(group)
                db.flush()
        if (action.result or {}).get("follow_up_id"):
            pending = db.get(CoachAction, action.result["follow_up_id"])
            if pending is not None and pending.status == "proposed":
                pending.status = "cancelled"
    else:
        # The exact inverse: each assignment back to its value before the
        # action (checked above to still hold the value the action left).
        items = action.result["assignments"]
        rows = _assignment_rows(db, user, action.command["month"], [i["category_id"] for i in items])
        for item in items:
            row = rows[item["category_id"]]
            row.assigned_cents = item["before_cents"]
            row.suggestion_state = "edited"
    action.status = "undone"
    action.undone_at = _now()
    db.flush()
    return action


def action_out(db: Session, user: User, action: CoachAction) -> dict:
    return {
        "id": action.id,
        "kind": action.kind,
        "status": action.status,
        "title": action.preview.get("title", ""),
        "command": action.command,
        "preview": action.preview,
        "revision": action.revision,
        "result": action.result,
        "created_at": action.created_at,
        "applied_at": action.applied_at,
        "undone_at": action.undone_at,
        "can_undo": can_undo(db, user, action),
    }


def command_from_input(db: Session, user: User, payload) -> dict:
    """A command from ids (a widget's Review adjustment, or an Edit), with the
    names the preview shows. Unknown ids are 404."""
    from . import schedules as sched
    from ..clock import today_madrid
    from ..models import Account

    names = dict(db.execute(
        select(Category.id, Category.name).where(Category.user_id == user.id, Category.archived.is_(False))
    ).all())

    def name(category_id: str | None) -> str | None:
        if category_id is None:
            return None
        if category_id not in names:
            raise ActionError(404, "category_not_found")
        return names[category_id]

    month = sched.current_month()
    if payload.kind == "moves":
        if not payload.moves:
            raise ActionError(422, "moves_required")
        return {"kind": "moves", "month": month, "moves": [
            {"from_category_id": m.from_category_id, "from_name": name(m.from_category_id),
             "to_category_id": m.to_category_id, "to_name": name(m.to_category_id),
             "amount_cents": m.amount_cents}
            for m in payload.moves
        ]}
    if payload.kind == "assignments":
        if not payload.items:
            raise ActionError(422, "items_required")
        return {"kind": "assignments", "month": month, "items": [
            {"category_id": i.category_id, "category_name": name(i.category_id), "amount_cents": i.amount_cents}
            for i in payload.items
        ]}
    if payload.amount_cents is None:
        raise ActionError(422, "amount_required")
    if payload.kind == "assignment":
        if payload.category_id is None:
            raise ActionError(422, "category_required")
        return {"kind": "assignment", "month": month, "category_id": payload.category_id,
                "category_name": name(payload.category_id), "amount_cents": payload.amount_cents}
    on = payload.date or today_madrid()
    account_name = None
    if payload.account_id:
        account_name = db.scalar(
            select(Account.name).where(Account.id == payload.account_id, Account.user_id == user.id)
        )
        if account_name is None:
            raise ActionError(404, "account_not_found")
    return {
        "kind": "transaction", "month": on.strftime("%Y-%m"), "direction": payload.direction,
        "amount_cents": payload.amount_cents, "category_id": payload.category_id,
        "category_name": name(payload.category_id), "payee": (payload.payee or "").strip() or None,
        "date": on.isoformat(), "account_id": payload.account_id, "account_name": account_name,
        "note": payload.note,
    }
