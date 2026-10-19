"""Who a token belongs to (spec: authentication, auth0-users design D3)."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Account, User


def _by_sub(db: Session, sub: str) -> User | None:
    return db.scalar(select(User).where(User.auth0_sub == sub))


def resolve(db: Session, sub: str, email: str | None) -> User:
    """By auth0_sub; else link the user with that email and no sub yet; else
    create one with a cash account, so the person starts at onboarding."""
    user = _by_sub(db, sub)
    if user is not None:
        return user
    if email:
        user = db.scalar(select(User).where(func.lower(User.email) == email, User.auth0_sub.is_(None)))
        if user is not None:
            user.auth0_sub = sub
            db.flush()
            return user
    try:
        # Savepoint: the first requests of a new person arrive in parallel
        # (Home and the conversation load together); the loser reuses it.
        with db.begin_nested():
            user = User(auth0_sub=sub, email=email or f"{sub}@users.olmenta.invalid", locale="es")
            db.add(user)
            db.flush()
            db.add(Account(user_id=user.id, name="Efectivo", type="cash"))
            db.flush()
    except IntegrityError:
        user = _by_sub(db, sub)
        if user is None:
            raise
    return user
