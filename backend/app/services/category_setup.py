"""Category tree creation shared by the dev seed and onboarding finalize.

Names are reused case-insensitively (mirroring payee resolution) instead of
erroring like the public categories API: onboarding runs against a tree that
may already hold seeded or previously created entries, and re-running must be
idempotent.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Category, CategoryGroup

# Default Spanish starter tree — the onboarding template fallback, and the
# dev-seed stand-in until the interview generates personalized trees.
# Mirrors the webapp mock (webapp/src/lib/mock-data.ts).
DEFAULT_CATEGORY_TREE: list[tuple[str, list[tuple[str, str]]]] = [
    ("Vivienda", [("Alquiler", "home"), ("Suministros", "zap")]),
    ("Comida", [("Supermercado", "shopping-bag"), ("Restaurantes", "coffee")]),
    ("Transporte", [("Gasolina", "flame"), ("Transporte público", "credit-card")]),
    (
        "Estilo de vida",
        [("Suscripciones", "receipt"), ("Ocio", "users"), ("Ahorro", "piggy-bank")],
    ),
]


def ensure_group(db: Session, user_id: str, name: str) -> tuple[CategoryGroup, bool]:
    """Find-or-create; the bool reports whether a new group was created."""
    trimmed = name.strip()
    group = db.scalar(
        select(CategoryGroup).where(
            CategoryGroup.user_id == user_id,
            func.lower(CategoryGroup.name) == trimmed.lower(),
        )
    )
    if group is not None:
        return group, False
    next_order = db.scalar(
        select(func.coalesce(func.max(CategoryGroup.sort_order), 0)).where(
            CategoryGroup.user_id == user_id
        )
    )
    group = CategoryGroup(user_id=user_id, name=trimmed, sort_order=(next_order or 0) + 1)
    db.add(group)
    db.flush()
    return group, True


def ensure_category(
    db: Session, user_id: str, group_id: str, name: str, icon: str = "circle"
) -> tuple[Category, bool]:
    """Find-or-create; the bool reports whether a new category was created."""
    trimmed = name.strip()
    category = db.scalar(
        select(Category).where(
            Category.user_id == user_id,
            Category.group_id == group_id,
            func.lower(Category.name) == trimmed.lower(),
        )
    )
    if category is not None:
        return category, False
    category = Category(user_id=user_id, group_id=group_id, name=trimmed, icon=icon)
    db.add(category)
    db.flush()
    return category, True


def create_tree(
    db: Session, user_id: str, tree: list[tuple[str, list[tuple[str, str]]]]
) -> int:
    """Idempotently create the tree; returns how many categories were created."""
    created = 0
    for group_name, categories in tree:
        group, _ = ensure_group(db, user_id, group_name)
        for category_name, icon in categories:
            _, was_created = ensure_category(db, user_id, group.id, category_name, icon)
            created += int(was_created)
    return created
