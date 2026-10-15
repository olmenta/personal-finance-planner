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
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BudgetAssignment, BudgetMonth, Category, CoachAction, CoachMessage, Transaction, User
from . import budget_moves, budget_view
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
    touched = _touched(command)
    before = _assigned(db, user, month, touched)
    if kind == "assignment":
        budget_moves.set_assignment(db, user, month, command["category_id"], command["amount_cents"])
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
    if isinstance(error, EntryError):
        return {"code": error.code, "status": error.status}
    detail = getattr(error, "detail", None)
    status = getattr(error, "status_code", 422)
    if isinstance(detail, dict) and "code" in detail:
        return {"code": detail["code"], "status": status}
    return {"code": "invalid_action", "status": 422}


REFUSALS = (budget_moves.MoveError, EntryError, HTTPException)


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
    month = command["month"]
    ids = _touched(command)
    before_view = budget_view.build_view(db, user, month)
    before = _category_rows(before_view, ids)
    error = None
    after_view = None
    savepoint = db.begin_nested()
    try:
        _apply(db, user, command)
        after_view = budget_view.build_view(db, user, month)
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
    if command["kind"] == "transaction":
        result["transaction"] = {
            key: command.get(key)
            for key in ("amount_cents", "direction", "category_name", "payee", "date", "account_name", "note")
        }
    return result


def title(command: dict) -> str:
    """Deterministic one-line description (English placeholder until next-intl)."""
    if command["kind"] == "transaction":
        verb = "Record income of" if command["direction"] == "income" else "Record"
        where = f" at {command['payee']}" if command.get("payee") else ""
        into = f" in {command['category_name']}" if command.get("category_name") else ""
        return f"{verb} {eur(command['amount_cents'])}{where}{into}"
    if command["kind"] == "assignment":
        return f"Set {command['category_name']} to {eur(command['amount_cents'])}"
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
        if widget.get("type") == "action_preview" and data.get("action_id") == old.id:
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


def commit(db: Session, user: User, action_id: str, revision: str, idempotency_key: str) -> CoachAction:
    action = get_action(db, user, action_id, lock=True)
    if action.status == "applied":
        if action.idempotency_key == idempotency_key:
            return action  # a retry of the same confirm: the recorded result
        raise ActionError(409, "already_applied")
    if action.status in ("cancelled", "undone"):
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
    savepoint = db.begin_nested()
    try:
        result = _apply(db, user, action.command)
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
