"""Widgets for coach messages (spec: coach-conversation, design D3).

The model only names widgets by `ref`; every number in a widget comes from
the engine here. A ref is accepted only if a tool produced it in the same
run, and a type that doesn't match its ref or isn't in the catalog is
dropped. Action widgets store the action id; their live state (status,
undo still possible) is merged in when messages are read.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Category, CoachAction, CoachMessage, Payee, Transaction, User
from . import coach, coach_actions
from .coach_tools import CoachDeps, future_payment_by_id

SCHEMA_VERSION = 1

WidgetType = Literal[
    "month_summary", "breakdown", "future_payment", "action_preview", "action_result",
    "coach_proposal", "transaction", "category_choice",
]

# ref prefix -> the widget type it builds
REF_TYPES = {
    "month": "month_summary",
    "breakdown": "breakdown",
    "future_payment": "future_payment",
    "action": "action_preview",
    "choice": "category_choice",
    "proposal": "coach_proposal",
    "transaction": "transaction",
}


# Widgets that show an action: their live state is merged in on read.
ACTION_WIDGETS = ("action_preview", "action_result", "category_choice")


class WidgetRef(BaseModel):
    type: str
    ref: str


def envelope(kind: str, data: dict, snapshot_version: str | None) -> dict:
    return {
        "type": kind,
        "schema_version": SCHEMA_VERSION,
        "snapshot_version": snapshot_version,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def _transaction(db: Session, user: User, txn_id: str) -> dict | None:
    row = db.execute(
        select(Transaction, Payee.name, Category.name, Account.name)
        .outerjoin(Payee, Payee.id == Transaction.payee_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .join(Account, Account.id == Transaction.account_id)
        .where(Transaction.id == txn_id, Transaction.user_id == user.id)
    ).first()
    if row is None:
        return None
    txn, payee, category, account = row
    return {"id": txn.id, "date": txn.date.isoformat(), "amount_cents": txn.amount_cents,
            "payee": payee, "category_name": category, "account_name": account,
            "description": txn.description}


def _data(deps: CoachDeps, kind: str, subject: str) -> dict | None:
    db, user = deps.db, deps.user
    match kind:
        case "month_summary":
            home = deps.get_home()
            return {"month": home.month, "status": home.status,
                    "reasons": [r.model_dump() for r in home.reasons],
                    "summary": home.summary.model_dump(), "future": home.future.model_dump()}
        case "breakdown":
            return {"summary": deps.get_home().summary.model_dump()}
        case "future_payment":
            return future_payment_by_id(db, user, deps.view(), subject)
        case "action_preview" | "category_choice":
            if any(a.id == subject for a in deps.actions):
                return {"action_id": subject}
            return None
        case "coach_proposal":
            proposal = next((p for p in coach.visible(db, user) if p.fingerprint == subject), None)
            return coach.proposal_out(proposal).model_dump() if proposal else None
        case "transaction":
            return _transaction(db, user, subject)
    return None


def build(deps: CoachDeps, refs: list[WidgetRef], snapshot_version: str | None) -> list[dict]:
    widgets: list[dict] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.ref in seen or ref.ref not in deps.refs:
            continue
        prefix, _, subject = ref.ref.partition(":")
        kind = REF_TYPES.get(prefix)
        if kind is None or ref.type != kind:
            continue
        data = _data(deps, kind, subject)
        if data is None:
            continue
        seen.add(ref.ref)
        widgets.append(envelope(kind, data, snapshot_version))
    return widgets


def with_live_actions(db: Session, user: User, messages: list[CoachMessage]) -> list[list[dict]]:
    """Each message's widgets with the current state of its actions."""
    ids = {
        (w.get("data") or {}).get("action_id")
        for m in messages for w in (m.widgets or [])
        if w.get("type") in ACTION_WIDGETS
    }
    ids.discard(None)
    actions = {
        a.id: coach_actions.action_out(db, user, a)
        for a in db.scalars(select(CoachAction).where(CoachAction.user_id == user.id,
                                                      CoachAction.id.in_(ids)))
    } if ids else {}
    result = []
    for m in messages:
        widgets = []
        for w in m.widgets or []:
            action_id = (w.get("data") or {}).get("action_id")
            if w.get("type") in ACTION_WIDGETS:
                if action_id not in actions:
                    continue
                w = {**w, "data": {**w["data"], "action": actions[action_id]}}
            widgets.append(w)
        result.append(widgets)
    return result
