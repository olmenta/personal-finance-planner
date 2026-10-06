"""Payee resolution shared by manual writes, imports, and bulk apply."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import IncomeSchedule, Payee, Transaction


def resolve_payee(db: Session, user_id: str, name: str | None) -> Payee | None:
    """Find-or-create the user's payee, case-insensitive on the trimmed name.

    Payees are born from transaction and income schedule writes — no
    POST /payees (design D2).
    Returns None for empty/whitespace-only input.
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


def delete_orphan_payees(db: Session, user_id: str, payee_ids: set[str]) -> int:
    """Delete the given payees when no transaction or income schedule
    references them anymore.

    Used by import-batch discard so rejected AI payee proposals don't
    linger in the autocomplete list.
    """
    if not payee_ids:
        return 0
    referenced = set(
        db.scalars(
            select(Transaction.payee_id).where(Transaction.payee_id.in_(payee_ids))
        )
    ) | set(
        db.scalars(
            select(IncomeSchedule.payee_id).where(IncomeSchedule.payee_id.in_(payee_ids))
        )
    )
    deleted = 0
    for payee in db.scalars(
        select(Payee).where(Payee.user_id == user_id, Payee.id.in_(payee_ids - referenced))
    ):
        db.delete(payee)
        deleted += 1
    db.flush()
    return deleted
