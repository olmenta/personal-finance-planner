"""Transfers between the user's accounts (spec: transfers).

Twin rows outside the budget plane; every mutation goes through
services/transfers.py so the pair invariants hold.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import today_madrid
from ..db import get_db
from ..deps import current_user
from ..models import Transaction, User
from ..schemas import TransferCreate, TransferOut, TransferUpdate
from ..services import transfers as service
from ..services.accounts import resolve_account

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _out(out: Transaction, inflow: Transaction) -> TransferOut:
    return TransferOut(
        pair_id=out.transfer_pair_id or "",
        from_account_id=out.account_id,
        to_account_id=inflow.account_id,
        amount_cents=inflow.amount_cents,
        date=out.date,
        note=out.description,
        out_transaction_id=out.id,
        in_transaction_id=inflow.id,
    )


@router.post(
    "",
    response_model=TransferOut,
    status_code=201,
    responses={422: {"description": "same_account"}, 404: {"description": "account_not_found"}},
)
def create_transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TransferOut:
    source = resolve_account(db, user.id, payload.from_account_id)
    target = resolve_account(db, user.id, payload.to_account_id)
    out, inflow = service.create_pair(
        db, source, target, payload.amount_cents, payload.date or today_madrid(), payload.note
    )
    return _out(out, inflow)


@router.get("/{pair_id}", response_model=TransferOut)
def get_transfer(
    pair_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TransferOut:
    return _out(*service.get_pair(db, user.id, pair_id))


@router.patch("/{pair_id}", response_model=TransferOut)
def update_transfer(
    pair_id: str,
    payload: TransferUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TransferOut:
    out, inflow = service.update_pair(
        db,
        user.id,
        pair_id,
        amount_cents=payload.amount_cents,
        on=payload.date,
        note=payload.note,
        note_set="note" in payload.model_fields_set,
    )
    return _out(out, inflow)


@router.delete("/{pair_id}", status_code=204)
def delete_transfer(
    pair_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    service.delete_pair(db, user.id, pair_id)


@router.post("/{pair_id}/unlink", status_code=204)
def unlink_transfer(
    pair_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    service.unlink_pair(db, user.id, pair_id)
