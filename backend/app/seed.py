"""Idempotent development seed.

Creates the single dev user, a default cash account and the default Spanish
category tree (stand-in until AI onboarding generates personalized trees).
No income is seeded — income arrives via the onboarding interview.

Run: uv run python -m app.seed
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session_factory
from .models import Account, User
from .services.category_setup import DEFAULT_CATEGORY_TREE, create_tree

DEV_USER_EMAIL = "dev@localhost"


def get_dev_user(session: Session) -> User | None:
    return session.scalar(select(User).where(User.email == DEV_USER_EMAIL))


def seed(session: Session) -> User:
    user = get_dev_user(session)
    if user is None:
        user = User(email=DEV_USER_EMAIL, locale="es")
        session.add(user)
        session.flush()

    account = session.scalar(select(Account).where(Account.user_id == user.id))
    if account is None:
        session.add(Account(user_id=user.id, name="Efectivo", type="cash"))

    create_tree(session, user.id, DEFAULT_CATEGORY_TREE)

    session.commit()
    return user


def main() -> None:
    with get_session_factory()() as session:
        user = seed(session)
        print(f"Seeded dev user {user.email} ({user.id})")


if __name__ == "__main__":
    main()
