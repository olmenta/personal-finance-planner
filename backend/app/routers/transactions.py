"""Manual transaction entry and listing."""

import hashlib
import uuid
from datetime import date as date_type
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Account, Category, Transaction, User
from ..schemas import TransactionCreate, TransactionOut

router = APIRouter(prefix="/transactions", tags=["transactions"])

MADRID = ZoneInfo("Europe/Madrid")


def today_madrid() -> date_type:
    return datetime.now(MADRID).date()


def dedupe_hash(
    account_id: str, txn_date: date_type, amount_cents: int, description: str | None, salt: str = ""
) -> str:
    raw = f"{account_id}|{txn_date.isoformat()}|{amount_cents}|{description or ''}|{salt}"
    return hashlib.sha256(raw.encode()).hexdigest()


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

    txn = Transaction(
        user_id=user.id,
        account_id=account.id,
        category_id=category.id,
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


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Transaction]:
    query = select(Transaction).where(Transaction.user_id == user.id)
    if month:
        year, mon = (int(p) for p in month.split("-"))
        start = date_type(year, mon, 1)
        end = date_type(year + 1, 1, 1) if mon == 12 else date_type(year, mon + 1, 1)
        query = query.where(Transaction.date >= start, Transaction.date < end)
    query = query.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    return list(db.scalars(query))
