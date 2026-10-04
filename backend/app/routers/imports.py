"""Bank statement import endpoints (design D6)."""

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..ingestion import StatementFormatError
from ..models import ImportBatch, User
from ..schemas import ConfirmImportRequest, ImportBatchView, StagedTransactionOut, TwinMatch
from ..services import import_batch as service
from ..services.accounts import resolve_account

router = APIRouter(prefix="/imports", tags=["imports"])


def _staged(db: Session, batch: ImportBatch) -> list[StagedTransactionOut]:
    matches = service.match_suggestions(db, batch)
    rows = []
    for txn in service.staged_rows(db, batch):
        row = StagedTransactionOut.model_validate(txn)
        match = matches.get(txn.id)
        if match is not None:
            row.match = TwinMatch(
                transaction_id=match.twin.id,
                pair_id=match.twin.transfer_pair_id or "",
                other_account_id=match.other_account_id or "",
                date=match.twin.date,
            )
        rows.append(row)
    return rows


def _view(db: Session, batch: ImportBatch) -> ImportBatchView:
    return ImportBatchView(
        id=batch.id,
        account_id=batch.account_id,
        source=batch.source,
        filename=batch.filename,
        status=batch.status,
        row_count=batch.row_count,
        skipped_duplicates=batch.skipped_duplicates,
        transactions=_staged(db, batch) if batch.status == "staged" else [],
    )


def _get_batch(db: Session, user: User, batch_id: str) -> ImportBatch:
    batch = db.scalar(
        select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.user_id == user.id)
    )
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found"})
    return batch


def _pending_batch(db: Session, user: User) -> ImportBatch | None:
    return db.scalar(
        select(ImportBatch).where(
            ImportBatch.user_id == user.id, ImportBatch.status == "staged"
        )
    )


@router.post(
    "",
    response_model=ImportBatchView,
    status_code=201,
    responses={
        409: {"description": "A staged batch already exists (import_pending)"},
        404: {"description": "Unknown or foreign account (account_not_found)"},
    },
)
async def upload_import(
    file: UploadFile = File(...),
    bank: Literal["bbva", "sabadell", "custom"] = Form(...),
    # Omitted = the user's main account.
    account_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ImportBatchView:
    # Single pending batch invariant (design D1): app-level guard, one writer.
    pending = _pending_batch(db, user)
    if pending is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "import_pending", "batch_id": pending.id},
        )

    content = await file.read()
    if len(content) > service.MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large"})

    account = resolve_account(db, user.id, account_id or None)

    try:
        batch = service.create_batch(
            db, user, account.id, bank, file.filename or "statement", content
        )
    except StatementFormatError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code}) from exc
    except service.TooManyRowsError as exc:
        raise HTTPException(status_code=413, detail={"code": "file_too_large"}) from exc
    return _view(db, batch)


# Declared before GET /{batch_id} so "pending" never routes as a batch id (design D2).
@router.get(
    "/pending",
    response_model=ImportBatchView,
    responses={404: {"description": "No staged batch (no_pending_import)"}},
)
def get_pending_import(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ImportBatchView:
    batch = _pending_batch(db, user)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "no_pending_import"})
    return _view(db, batch)


@router.get("/{batch_id}", response_model=ImportBatchView)
def get_import(
    batch_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ImportBatchView:
    return _view(db, _get_batch(db, user, batch_id))


@router.post("/{batch_id}/confirm", response_model=ImportBatchView)
def confirm_import(
    batch_id: str,
    payload: ConfirmImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ImportBatchView:
    batch = _get_batch(db, user, batch_id)
    try:
        service.confirm_batch(
            db,
            user,
            batch,
            payload.overrides,
            payload.payee_overrides,
            payload.transfer_overrides,
            payload.accept_matches,
        )
    except service.BatchNotStagedError as exc:
        raise HTTPException(status_code=409, detail={"code": "batch_not_staged"}) from exc
    return _view(db, batch)


@router.delete("/{batch_id}", status_code=204)
def discard_import(
    batch_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    batch = _get_batch(db, user, batch_id)
    try:
        service.discard_batch(db, batch)
    except service.BatchNotStagedError as exc:
        raise HTTPException(status_code=409, detail={"code": "batch_not_staged"}) from exc
