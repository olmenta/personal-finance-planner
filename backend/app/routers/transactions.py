"""Manual transaction entry and listing."""

import uuid
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import today_madrid
from ..db import get_db
from ..deps import current_user
from ..ingestion import NormalizedTransaction
from ..models import Category, Transaction, User
from ..schemas import (
    ReviewApplyRequest,
    ReviewApplyResponse,
    ReviewRowOut,
    ReviewView,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from ..services import category_suggestions, review
from ..services.accounts import resolve_account
from ..services.hashing import dedupe_hash
from ..services.payees import delete_orphan_payees, resolve_payee
from ..services.transfers import annotate_counterparts

router = APIRouter(prefix="/transactions", tags=["transactions"])


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

    account = resolve_account(db, user.id, payload.account_id)

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


REVIEW_ROW_CAP = 500


def _reviewable(db: Session, user: User):
    """Confirmed rows still waiting for a category: not transfer twins, not
    opening balances (a card's pre-existing debt is not spending)."""
    return select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.status == "confirmed",
        Transaction.category_id.is_(None),
        Transaction.transfer_pair_id.is_(None),
        Transaction.source != "opening_balance",
    )


@router.post("/review", response_model=ReviewView)
def review_uncategorized(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ReviewView:
    """Every uncategorized transaction (all months, newest first), with the
    AI's suggestion as a default and any twin match — writing nothing.

    POST despite being a read: one model call, seconds of latency — keep it
    out of caches and prefetchers. AI failure degrades to no suggestions.
    """
    txns = list(
        db.scalars(
            _reviewable(db, user)
            .order_by(Transaction.date.desc(), Transaction.created_at.desc())
            .limit(REVIEW_ROW_CAP)
        )
    )
    if not txns:
        return ReviewView(transactions=[])

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
    matches = review.twin_matches(db, txns)

    out: list[ReviewRowOut] = []
    for index, txn in enumerate(txns):
        row = ReviewRowOut.model_validate(txn)
        suggestion = suggestions.get(index, category_suggestions.EMPTY)
        if suggestion.category_id or suggestion.payee:
            row.suggested_category_id = suggestion.category_id
            row.suggested_payee = suggestion.payee
            row.confidence = suggestion.confidence
        if (match := matches.get(txn.id)) is not None:
            row.match = review.twin_match_out(match)
        out.append(row)
    return ReviewView(transactions=out)


@router.post("/review/apply", response_model=ReviewApplyResponse)
def apply_review(
    payload: ReviewApplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ReviewApplyResponse:
    """Apply the review's decisions with the import's semantics, only to the
    user's confirmed uncategorized rows; anything else is skipped."""
    ids = (
        set(payload.overrides)
        | set(payload.payee_overrides)
        | set(payload.note_overrides)
        | set(payload.transfer_overrides)
        | set(payload.accept_matches)
    )
    if not ids:
        return ReviewApplyResponse(applied=0)
    rows = list(db.scalars(_reviewable(db, user).where(Transaction.id.in_(ids))))
    replaced, applied = review.apply_decisions(
        db,
        user,
        rows,
        review.Decisions(
            overrides=payload.overrides,
            payee_overrides=payload.payee_overrides,
            note_overrides=payload.note_overrides,
            transfer_overrides=payload.transfer_overrides,
            accept_matches=payload.accept_matches,
        ),
    )
    # Payees the review replaced must not linger in autocomplete.
    delete_orphan_payees(db, user.id, replaced)
    return ReviewApplyResponse(applied=applied)


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
    if txn.transfer_pair_id:
        # Twin invariants live in the transfer contract (PATCH /transfers).
        raise HTTPException(status_code=409, detail={"code": "is_transfer"})

    if payload.account_id is not None:
        txn.account_id = resolve_account(db, user.id, payload.account_id).id

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
    if txn.transfer_pair_id:
        raise HTTPException(status_code=409, detail={"code": "is_transfer"})
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
    return annotate_counterparts(db, list(db.scalars(query)))
