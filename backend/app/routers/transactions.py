"""Manual transaction entry and listing."""

import hashlib
import uuid
from datetime import date as date_type
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Account, Category, Payee, Transaction, User
from ..schemas import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])

MADRID = ZoneInfo("Europe/Madrid")


def today_madrid() -> date_type:
    return datetime.now(MADRID).date()


def dedupe_hash(
    account_id: str, txn_date: date_type, amount_cents: int, description: str | None, salt: str = ""
) -> str:
    raw = f"{account_id}|{txn_date.isoformat()}|{amount_cents}|{description or ''}|{salt}"
    return hashlib.sha256(raw.encode()).hexdigest()


def resolve_payee(db: Session, user_id: str, name: str | None) -> Payee | None:
    """Find-or-create the user's payee, case-insensitive on the trimmed name.

    Payees are born from transaction writes — no POST /payees (design D2).
    Returns None for empty/whitespace-only input.
    Reconciliation note: when edit-delete-transactions lands, wire this into
    PATCH /transactions/{id} too (empty string clears payee_id).
    """
    trimmed = (name or "").strip()
    if not trimmed:
        return None
    payee = db.scalar(
        select(Payee).where(
            Payee.user_id == user_id, func.lower(Payee.name) == trimmed.lower()
        )
    )
    if payee is None:
        payee = Payee(user_id=user_id, name=trimmed)
        db.add(payee)
        db.flush()
    return payee


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Transaction:
    category = db.scalar(
        select(Category).where(Category.id == payload.category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail={"code": "category_not_found"})

    account = db.scalar(select(Account).where(Account.user_id == user.id))
    if account is None:
        raise HTTPException(status_code=503, detail={"code": "account_not_seeded"})

    txn_date = payload.date or today_madrid()
    signed = payload.amount_cents if payload.kind == "income" else -payload.amount_cents
    payee = resolve_payee(db, user.id, payload.payee)

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
        payee_id=payee.id if payee else None,
        date=txn_date,
        amount_cents=signed,
        description=payload.note,
        source="manual",
        status="confirmed",
        # Manual entries get a per-row salt: two identical coffees the same day
        # are legitimate. Strict hashing applies to imported sources (§6.3).
        dedupe_hash=dedupe_hash(account.id, txn_date, signed, payload.note, salt=str(uuid.uuid4())),
    )
    db.add(txn)
    db.flush()
    return txn


def get_confirmed_or_404(db: Session, user_id: str, txn_id: str) -> Transaction:
    """Resolve by id + owner + confirmed; 404 otherwise (design D3).

    Staged import rows are managed only through the batch review, and a 404
    (not 403/409) avoids leaking other users' row ids.
    """
    txn = db.scalar(
        select(Transaction).where(
            Transaction.id == txn_id,
            Transaction.user_id == user_id,
            Transaction.status == "confirmed",
        )
    )
    if txn is None:
        raise HTTPException(status_code=404, detail={"code": "transaction_not_found"})
    return txn


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(
    txn_id: str,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Transaction:
    txn = get_confirmed_or_404(db, user.id, txn_id)

    if payload.category_id is not None:
        category = db.scalar(
            select(Category).where(
                Category.id == payload.category_id, Category.user_id == user.id
            )
        )
        if category is None:
            raise HTTPException(status_code=404, detail={"code": "category_not_found"})
        txn.category_id = category.id

    # Create-like amount semantics: positive magnitude + direction, signed
    # here. Without `kind` the row's current sign is kept (design D1).
    if payload.amount_cents is not None or payload.kind is not None:
        magnitude = (
            payload.amount_cents
            if payload.amount_cents is not None
            else abs(txn.amount_cents)
        )
        if payload.kind is not None:
            negative = payload.kind == "expense"
        else:
            negative = txn.amount_cents < 0
        txn.amount_cents = -magnitude if negative else magnitude

    if "note" in payload.model_fields_set:  # null clears the description
        txn.description = payload.note

    if "payee" in payload.model_fields_set:  # "" (or null) clears the payee
        # Relationship assignment (not the FK) so the already-loaded
        # `txn.payee` reflects the change in the response serialization.
        txn.payee = resolve_payee(db, user.id, payload.payee)

    if payload.date is not None:
        txn.date = payload.date

    # dedupe_hash deliberately untouched: edited imported rows must keep
    # colliding with re-imports of the same bank file (design D2).
    db.flush()
    return txn


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(
    txn_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    # Hard delete (design D4): totals are computed on read, nothing references
    # confirmed rows, and GDPR favors actual removal.
    txn = get_confirmed_or_404(db, user.id, txn_id)
    db.delete(txn)
    db.flush()


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Transaction]:
    # Staged import rows are visible only through the import batch view.
    query = select(Transaction).where(
        Transaction.user_id == user.id, Transaction.status == "confirmed"
    )
    if month:
        year, mon = (int(p) for p in month.split("-"))
        start = date_type(year, mon, 1)
        end = date_type(year + 1, 1, 1) if mon == 12 else date_type(year, mon + 1, 1)
        query = query.where(Transaction.date >= start, Transaction.date < end)
    query = query.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    return list(db.scalars(query))
