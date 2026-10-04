"""Transfers: two linked twin rows (design D1) — the single write path.

Invariants, enforced only here:

    amount(out) = −amount(in)        category_id = NULL, payee_id = NULL on both
    date equal on both               edit amount/date/note → both rows
    delete one → delete both         unlink → clear pair id on both

Callers run inside the request transaction (get_db commits/rolls back), so
a pair is always written or removed atomically.
"""

import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Transaction
from .hashing import dedupe_hash


def _twin(account: Account, pair_id: str, on: date, cents: int, note: str | None) -> Transaction:
    return Transaction(
        user_id=account.user_id,
        account_id=account.id,
        category_id=None,
        payee_id=None,
        date=on,
        amount_cents=cents,
        description=note,
        source="manual",
        status="confirmed",
        transfer_pair_id=pair_id,
        dedupe_hash=dedupe_hash(account.id, on, cents, note, salt=str(uuid.uuid4())),
    )


def create_pair(
    db: Session,
    source: Account,
    target: Account,
    amount_cents: int,
    on: date,
    note: str | None = None,
) -> tuple[Transaction, Transaction]:
    """Outflow in `source`, inflow in `target`; returns (out, in)."""
    if source.id == target.id:
        raise HTTPException(status_code=422, detail={"code": "same_account"})
    pair_id = str(uuid.uuid4())
    out = _twin(source, pair_id, on, -amount_cents, note)
    inflow = _twin(target, pair_id, on, amount_cents, note)
    db.add_all([out, inflow])
    db.flush()
    return out, inflow


def link_existing(db: Session, near: Transaction, target: Account) -> Transaction:
    """Turn an existing row (e.g. a staged import row being confirmed) into
    the near side of a new pair, creating its confirmed twin in `target`."""
    if near.account_id == target.id:
        raise HTTPException(status_code=422, detail={"code": "same_account"})
    pair_id = str(uuid.uuid4())
    near.transfer_pair_id = pair_id
    near.category_id = None
    near.payee_id = None
    twin = _twin(target, pair_id, near.date, -near.amount_cents, near.description)
    db.add(twin)
    db.flush()
    return twin


def get_pair(db: Session, user_id: str, pair_id: str) -> tuple[Transaction, Transaction]:
    """(out, in) of the user's pair; 404 `transfer_not_found` otherwise."""
    rows = list(
        db.scalars(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.transfer_pair_id == pair_id,
                Transaction.status == "confirmed",
            )
        )
    )
    if len(rows) != 2:
        raise HTTPException(status_code=404, detail={"code": "transfer_not_found"})
    out, inflow = sorted(rows, key=lambda t: t.amount_cents)
    return out, inflow


def update_pair(
    db: Session,
    user_id: str,
    pair_id: str,
    *,
    amount_cents: int | None = None,
    on: date | None = None,
    note: str | None = None,
    note_set: bool = False,
) -> tuple[Transaction, Transaction]:
    """Mirrored edit; dedupe hashes stay immutable like any edited row."""
    out, inflow = get_pair(db, user_id, pair_id)
    for row in (out, inflow):
        if amount_cents is not None:
            row.amount_cents = -amount_cents if row is out else amount_cents
        if on is not None:
            row.date = on
        if note_set:
            row.description = note
    db.flush()
    return out, inflow


def delete_pair(db: Session, user_id: str, pair_id: str) -> None:
    for row in get_pair(db, user_id, pair_id):
        db.delete(row)
    db.flush()


def unlink_pair(db: Session, user_id: str, pair_id: str) -> tuple[Transaction, Transaction]:
    """Both rows become independent uncategorized transactions."""
    out, inflow = get_pair(db, user_id, pair_id)
    out.transfer_pair_id = None
    inflow.transfer_pair_id = None
    db.flush()
    return out, inflow


def annotate_counterparts(db: Session, rows: list[Transaction]) -> list[Transaction]:
    """Set `transfer_account_id` (the other twin's account) on transfer rows,
    one query for the whole list."""
    pair_ids = {t.transfer_pair_id for t in rows if t.transfer_pair_id}
    if not pair_ids:
        return rows
    sides: dict[str, list[tuple[str, str]]] = {}
    for txn_id, pair_id, account_id in db.execute(
        select(Transaction.id, Transaction.transfer_pair_id, Transaction.account_id).where(
            Transaction.transfer_pair_id.in_(pair_ids)
        )
    ):
        sides.setdefault(pair_id, []).append((txn_id, account_id))
    for txn in rows:
        if txn.transfer_pair_id:
            txn.transfer_account_id = next(
                (acc for tid, acc in sides.get(txn.transfer_pair_id, []) if tid != txn.id), None
            )
    return rows
