"""Payee list with category memory (spec: payees, design D3).

Payees are created from transaction writes (see routers/transactions.py
resolve_payee) — this router only reads. The list is small (< a few hundred),
so the client filters locally; no server-side search.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Payee, Transaction, User
from ..schemas import PayeeOut

router = APIRouter(prefix="/payees", tags=["payees"])


@router.get("", response_model=list[PayeeOut])
def list_payees(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[PayeeOut]:
    # Newest confirmed transaction per payee carries the category memory.
    last_txn = (
        select(
            Transaction.payee_id,
            Transaction.category_id,
            Transaction.date,
            Transaction.created_at,
            func.row_number()
            .over(
                partition_by=Transaction.payee_id,
                order_by=(Transaction.date.desc(), Transaction.created_at.desc()),
            )
            .label("rn"),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.status == "confirmed",
            Transaction.payee_id.is_not(None),
        )
        .subquery()
    )

    rows = db.execute(
        select(Payee.id, Payee.name, last_txn.c.category_id)
        .outerjoin(last_txn, (last_txn.c.payee_id == Payee.id) & (last_txn.c.rn == 1))
        .where(Payee.user_id == user.id)
        .order_by(
            last_txn.c.date.desc().nulls_last(),
            last_txn.c.created_at.desc().nulls_last(),
            Payee.name,
        )
    ).all()

    return [
        PayeeOut(id=payee_id, name=name, last_category_id=category_id)
        for payee_id, name, category_id in rows
    ]
