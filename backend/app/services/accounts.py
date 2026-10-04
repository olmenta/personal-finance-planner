"""Accounts: main-account resolution, creation, derived balances (spec:
accounts-api, credit-cards).

Balances are never stored — an account's balance is the sum of its confirmed
transactions. A credit account owns one system payment category ("Pago
<card>") inside the "Tarjetas de crédito" system group; both are created
here, in the caller's transaction, and follow the account's rename/archive.
"""

import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Account, Category, CategoryGroup, Transaction
from .hashing import dedupe_hash

CARD_GROUP_NAME = "Tarjetas de crédito"
PAYMENT_PREFIX = "Pago "
PAYMENT_DAY_TOLERANCE = 2


def account_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "account_not_found"})


def active_accounts(db: Session, user_id: str) -> list[Account]:
    """Oldest first — the first one is the main account (design D4)."""
    return list(
        db.scalars(
            select(Account)
            .where(Account.user_id == user_id, Account.archived.is_(False))
            .order_by(Account.created_at, Account.id)
        )
    )


def main_account(db: Session, user_id: str) -> Account:
    accounts = active_accounts(db, user_id)
    if not accounts:
        raise HTTPException(status_code=503, detail={"code": "account_not_seeded"})
    return accounts[0]


def resolve_account(db: Session, user_id: str, account_id: str | None) -> Account:
    """The requested owned account, or the main account when omitted.
    Unknown or foreign ids are 404 `account_not_found`."""
    if account_id is None:
        return main_account(db, user_id)
    account = db.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    if account is None:
        raise account_not_found()
    return account


def find_by_name(db: Session, user_id: str, name: str) -> Account | None:
    return db.scalar(
        select(Account).where(
            Account.user_id == user_id,
            Account.archived.is_(False),
            func.lower(Account.name) == name.strip().lower(),
        )
    )


def ensure_card_group(db: Session, user_id: str) -> CategoryGroup:
    group = db.scalar(
        select(CategoryGroup).where(
            CategoryGroup.user_id == user_id, CategoryGroup.system.is_(True)
        )
    )
    if group is not None:
        return group
    next_order = db.scalar(
        select(func.coalesce(func.max(CategoryGroup.sort_order), 0)).where(
            CategoryGroup.user_id == user_id
        )
    )
    group = CategoryGroup(
        user_id=user_id, name=CARD_GROUP_NAME, sort_order=(next_order or 0) + 1, system=True
    )
    db.add(group)
    db.flush()
    return group


def payment_category(db: Session, account_id: str) -> Category | None:
    return db.scalar(select(Category).where(Category.payment_account_id == account_id))


def write_opening_balance(db: Session, account: Account, cents: int, on: date) -> Transaction:
    """Confirmed, uncategorized, salted like a manual entry (design D3)."""
    txn = Transaction(
        user_id=account.user_id,
        account_id=account.id,
        date=on,
        amount_cents=cents,
        source="opening_balance",
        status="confirmed",
        dedupe_hash=dedupe_hash(account.id, on, cents, None, salt=str(uuid.uuid4())),
    )
    db.add(txn)
    db.flush()
    return txn


def create_account(
    db: Session,
    user_id: str,
    *,
    name: str,
    type: str,
    institution: str | None = None,
    opening_balance_cents: int | None = None,
    payment_day: int | None = None,
    today: date,
) -> Account:
    """Create the account (409 `account_exists` on an active duplicate name),
    its payment category when it's a card, and its opening balance."""
    name = name.strip()
    if find_by_name(db, user_id, name) is not None:
        raise HTTPException(status_code=409, detail={"code": "account_exists"})
    account = Account(
        user_id=user_id,
        name=name,
        type=type,
        institution=institution,
        payment_day=payment_day if type == "credit" else None,
    )
    db.add(account)
    db.flush()
    if type == "credit":
        group = ensure_card_group(db, user_id)
        db.add(
            Category(
                user_id=user_id,
                group_id=group.id,
                name=f"{PAYMENT_PREFIX}{name}",
                icon="credit-card",
                payment_account_id=account.id,
            )
        )
        db.flush()
    if opening_balance_cents:
        write_opening_balance(db, account, opening_balance_cents, today)
    return account


def sync_payment_category(db: Session, account: Account) -> None:
    """Payment category follows the card's name and archived flag."""
    category = payment_category(db, account.id)
    if category is None:
        return
    category.name = f"{PAYMENT_PREFIX}{account.name}"
    category.archived = account.archived


def balances(db: Session, user_id: str) -> dict[str, int]:
    """account_id -> derived balance, one grouped query (staged rows excluded)."""
    return {
        account_id: int(total)
        for account_id, total in db.execute(
            select(Transaction.account_id, func.sum(Transaction.amount_cents))
            .where(Transaction.user_id == user_id, Transaction.status == "confirmed")
            .group_by(Transaction.account_id)
        )
    }


def suggest_payment_day(days: list[int]) -> int | None:
    """Earliest day of the first cluster of ≥2 payments whose day-of-month
    lies within ±2 days of each other (design D9); None otherwise."""
    ordered = sorted(days)
    for i, anchor in enumerate(ordered):
        cluster = [d for d in ordered[i:] if d - anchor <= PAYMENT_DAY_TOLERANCE]
        if len(cluster) >= 2:
            return anchor
    return None


def card_payment_days(db: Session, user_id: str) -> dict[str, list[int]]:
    """credit account_id -> day-of-month of each confirmed transfer inflow."""
    result: dict[str, list[int]] = {}
    for account_id, day in db.execute(
        select(Transaction.account_id, Transaction.date)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == "confirmed",
            Transaction.transfer_pair_id.is_not(None),
            Transaction.amount_cents > 0,
            Account.type == "credit",
        )
    ):
        result.setdefault(account_id, []).append(day.day)
    return result
