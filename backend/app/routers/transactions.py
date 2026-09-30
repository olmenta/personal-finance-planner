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
from ..ingestion import NormalizedTransaction
from ..models import Account, Category, Transaction, User
from ..schemas import (
    ApplyCategoriesRequest,
    ApplyCategoriesResponse,
    CategoryProposal,
    SuggestCategoriesRequest,
    SuggestCategoriesResponse,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from ..services import category_suggestions
from ..services.payees import resolve_payee

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
    category = None
    if payload.category_id is None:
        if payload.kind == "expense":
            raise HTTPException(status_code=422, detail={"code": "category_required"})
    else:
        category = db.scalar(
            select(Category).where(
                Category.id == payload.category_id, Category.user_id == user.id
            )
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
        category_id=category.id if category else None,
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


SUGGEST_ROW_CAP = 500


@router.post("/suggest-categories", response_model=SuggestCategoriesResponse)
def suggest_categories(
    payload: SuggestCategoriesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SuggestCategoriesResponse:
    """Propose categories + payees without writing anything (design D2/D3).

    POST despite being a read: one model call, seconds of latency — keep it
    out of caches and prefetchers. AI failure degrades to an empty list.
    """
    query = select(Transaction).where(
        Transaction.user_id == user.id, Transaction.status == "confirmed"
    )
    if payload.transaction_ids:
        query = query.where(Transaction.id.in_(payload.transaction_ids))
    else:
        query = query.where(Transaction.category_id.is_(None))
    query = query.order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(
        SUGGEST_ROW_CAP
    )
    txns = list(db.scalars(query))
    if not txns:
        return SuggestCategoriesResponse(proposals=[])

    categories = list(
        db.scalars(
            select(Category).where(Category.user_id == user.id, Category.archived.is_(False))
        )
    )
    rows = [
        NormalizedTransaction(
            date=txn.date,
            amount_cents=txn.amount_cents,
            currency=txn.currency,
            description=txn.description or txn.payee_name or "",
            category_hint=None,
        )
        for txn in txns
    ]
    history = category_suggestions.sample_history(db, user.id)
    suggestions = category_suggestions.suggest(categories, rows, history)

    proposals = [
        CategoryProposal(
            transaction_id=txn.id,
            category_id=suggestion.category_id,
            payee=suggestion.payee,
            confidence=suggestion.confidence,
        )
        for index, txn in enumerate(txns)
        if (suggestion := suggestions.get(index, category_suggestions.EMPTY)).category_id
        or suggestion.payee
    ]
    return SuggestCategoriesResponse(proposals=proposals)


@router.post("/apply-categories", response_model=ApplyCategoriesResponse)
def apply_categories(
    payload: ApplyCategoriesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ApplyCategoriesResponse:
    """Write the accepted assignments; invalid entries are skipped (design D2)."""
    valid_category_ids = set(
        db.scalars(select(Category.id).where(Category.user_id == user.id))
    )
    applied = 0
    for txn_id, assignment in payload.assignments.items():
        txn = db.scalar(
            select(Transaction).where(
                Transaction.id == txn_id,
                Transaction.user_id == user.id,
                Transaction.status == "confirmed",
            )
        )
        if txn is None:
            continue  # vanished or foreign row — skip, never fail the batch
        if assignment.category_id is not None and assignment.category_id not in valid_category_ids:
            continue
        if assignment.category_id is None and assignment.payee is None:
            continue
        if assignment.category_id is not None:
            txn.category_id = assignment.category_id
        if assignment.payee is not None:  # "" clears, name find-or-creates
            txn.payee = resolve_payee(db, user.id, assignment.payee)
        applied += 1
    db.flush()
    return ApplyCategoriesResponse(applied=applied)


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

    # Explicit null clears the category (un-marks a refund); absent leaves it.
    if "category_id" in payload.model_fields_set:
        if payload.category_id is None:
            txn.category_id = None
        else:
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
