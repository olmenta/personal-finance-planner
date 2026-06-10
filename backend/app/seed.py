"""Idempotent development seed.

Creates the single dev user, a default cash account and the default Spanish
category tree (stand-in until AI onboarding generates personalized trees).
No income is seeded — income arrives via the onboarding interview.

Run: uv run python -m app.seed
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session_factory
from .models import Account, Category, CategoryGroup, User

DEV_USER_EMAIL = "dev@localhost"

# Mirrors the webapp mock (webapp/src/lib/mock-data.ts).
CATEGORY_TREE: list[tuple[str, list[tuple[str, str]]]] = [
    ("Vivienda", [("Alquiler", "home"), ("Suministros", "zap")]),
    ("Comida", [("Supermercado", "shopping-bag"), ("Restaurantes", "coffee")]),
    ("Transporte", [("Gasolina", "flame"), ("Transporte público", "credit-card")]),
    (
        "Estilo de vida",
        [("Suscripciones", "receipt"), ("Ocio", "users"), ("Ahorro", "piggy-bank")],
    ),
]


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

    for sort_order, (group_name, categories) in enumerate(CATEGORY_TREE, start=1):
        group = session.scalar(
            select(CategoryGroup).where(
                CategoryGroup.user_id == user.id, CategoryGroup.name == group_name
            )
        )
        if group is None:
            group = CategoryGroup(user_id=user.id, name=group_name, sort_order=sort_order)
            session.add(group)
            session.flush()
        for cat_name, icon in categories:
            exists = session.scalar(
                select(Category).where(
                    Category.user_id == user.id,
                    Category.group_id == group.id,
                    Category.name == cat_name,
                )
            )
            if exists is None:
                session.add(
                    Category(user_id=user.id, group_id=group.id, name=cat_name, icon=icon)
                )

    session.commit()
    return user


def main() -> None:
    with get_session_factory()() as session:
        user = seed(session)
        print(f"Seeded dev user {user.email} ({user.id})")


if __name__ == "__main__":
    main()
