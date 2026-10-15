"""Manual transaction entry, shared by POST /transactions and the coach
(coach-conversation design D6)."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import today_madrid
from ..models import Category, Transaction, User
from .accounts import resolve_account
from .hashing import dedupe_hash
from .payees import resolve_payee


class EntryError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def create_entry(
    db: Session,
    user: User,
    *,
    amount_cents: int,
    kind: str,
    category_id: str | None,
    account_id: str | None,
    payee: str | None,
    note: str | None,
    on: date | None,
) -> Transaction:
    """A confirmed manual expense or income. Expenses need a category; an
    income without one funds To Be Assigned."""
    category = None
    if category_id is None:
        if kind == "expense":
            raise EntryError(422, "category_required")
    else:
        category = db.scalar(
            select(Category).where(Category.id == category_id, Category.user_id == user.id)
        )
        if category is None:
            raise EntryError(404, "category_not_found")
    account = resolve_account(db, user.id, account_id)
    txn_date = on or today_madrid()
    signed = amount_cents if kind == "income" else -amount_cents
    resolved = resolve_payee(db, user.id, payee)
    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id if category else None,
        payee_id=resolved.id if resolved else None,
        date=txn_date,
        amount_cents=signed,
        description=note,
        source="manual",
        status="confirmed",
        # Manual entries get a per-row salt: two identical coffees the same day
        # are legitimate. Strict hashing applies to imported sources (§6.3).
        dedupe_hash=dedupe_hash(account.id, txn_date, signed, note, salt=str(uuid.uuid4())),
    )
    db.add(txn)
    db.flush()
    return txn
