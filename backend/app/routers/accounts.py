"""Accounts: list with derived balances, create, edit (spec: accounts-api,
credit-cards). No delete — archiving hides an account from pickers while its
transactions keep counting."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import current_month, today_madrid
from ..db import get_db
from ..deps import current_user
from ..models import Account, User
from ..schemas import AccountCreate, AccountOut, AccountUpdate
from ..services import accounts as service
from ..services.budget_view import payment_available_by_card

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _list(db: Session, user: User) -> list[AccountOut]:
    rows = list(
        db.scalars(
            select(Account).where(Account.user_id == user.id).order_by(Account.created_at, Account.id)
        )
    )
    balances = service.balances(db, user.id)
    main_id = next((a.id for a in rows if not a.archived), None)
    has_cards = any(a.type == "credit" for a in rows)
    payment_available = payment_available_by_card(db, user, current_month()) if has_cards else {}
    payment_days = service.card_payment_days(db, user.id) if has_cards else {}
    result = []
    for account in rows:
        balance = balances.get(account.id, 0)
        out = AccountOut(
            id=account.id,
            name=account.name,
            type=account.type,  # type: ignore[arg-type]
            institution=account.institution,
            archived=account.archived,
            balance_cents=balance,
            is_main=account.id == main_id,
        )
        if account.type == "credit":
            category = service.payment_category(db, account.id)
            available = payment_available.get(account.id, 0)
            out.payment_day = account.payment_day
            out.suggested_payment_day = (
                None
                if account.payment_day is not None
                else service.suggest_payment_day(payment_days.get(account.id, []))
            )
            out.payment_category_id = category.id if category else None
            out.payment_available_cents = available
            out.uncovered_debt_cents = max(0, -balance - available)
        result.append(out)
    return result


def _get_owned(db: Session, user: User, account_id: str) -> Account:
    account = db.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    )
    if account is None:
        raise service.account_not_found()
    return account


def _out(db: Session, user: User, account_id: str) -> AccountOut:
    return next(a for a in _list(db, user) if a.id == account_id)


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AccountOut]:
    return _list(db, user)


@router.post(
    "",
    response_model=AccountOut,
    status_code=201,
    responses={409: {"description": "Active account with that name (account_exists)"}},
)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AccountOut:
    if payload.payment_day is not None and payload.type != "credit":
        raise HTTPException(status_code=422, detail={"code": "payment_day_credit_only"})
    account = service.create_account(
        db,
        user.id,
        name=payload.name,
        type=payload.type,
        institution=payload.institution,
        opening_balance_cents=payload.opening_balance_cents,
        payment_day=payload.payment_day,
        today=today_madrid(),
    )
    return _out(db, user, account.id)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: str,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AccountOut:
    account = _get_owned(db, user, account_id)
    fields = payload.model_fields_set
    if payload.name is not None:
        name = payload.name.strip()
        duplicate = service.find_by_name(db, user.id, name)
        if duplicate is not None and duplicate.id != account.id:
            raise HTTPException(status_code=409, detail={"code": "account_exists"})
        account.name = name
    if "institution" in fields:
        account.institution = payload.institution
    if payload.archived is False and account.archived:
        # Unarchiving must not create a second active account with the name.
        duplicate = service.find_by_name(db, user.id, account.name)
        if duplicate is not None:
            raise HTTPException(status_code=409, detail={"code": "account_exists"})
    if payload.archived is not None:
        account.archived = payload.archived
    if "payment_day" in fields:
        if account.type != "credit":
            raise HTTPException(status_code=422, detail={"code": "payment_day_credit_only"})
        account.payment_day = payload.payment_day
    service.sync_payment_category(db, account)
    db.flush()
    return _out(db, user, account.id)
