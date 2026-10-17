"""Creating categories and groups, shared by the categories API and the
coach (coach-budget-setup design D2). Same rules and codes as the API."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Category, CategoryGroup


class CategoryError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def get_group(db: Session, user_id: str, group_id: str) -> CategoryGroup:
    group = db.scalar(select(CategoryGroup).where(CategoryGroup.id == group_id, CategoryGroup.user_id == user_id))
    if group is None:
        raise CategoryError(404, "group_not_found")
    return group


def ensure_name_free_in_group(
    db: Session, user_id: str, group_id: str, name: str, exclude_id: str | None = None
) -> None:
    """Per-group unique names, case-insensitive (categories design D3).
    Different groups may share a name ("Seguro" under Coche and Casa)."""
    query = select(Category).where(
        Category.user_id == user_id,
        Category.group_id == group_id,
        func.lower(Category.name) == name.lower(),
    )
    if exclude_id:
        query = query.where(Category.id != exclude_id)
    if db.scalar(query) is not None:
        raise CategoryError(409, "category_exists")


def ensure_group_name_free(db: Session, user_id: str, name: str, exclude_id: str | None = None) -> None:
    query = select(CategoryGroup).where(
        CategoryGroup.user_id == user_id,
        func.lower(CategoryGroup.name) == name.lower(),
    )
    if exclude_id:
        query = query.where(CategoryGroup.id != exclude_id)
    if db.scalar(query) is not None:
        raise CategoryError(409, "group_exists")


def create_category(
    db: Session, user_id: str, group_id: str, name: str, icon: str = "circle", savings: bool = False
) -> Category:
    group = get_group(db, user_id, group_id)
    if group.system:
        raise CategoryError(409, "payment_category_locked")
    name = name.strip()
    ensure_name_free_in_group(db, user_id, group.id, name)
    category = Category(
        user_id=user_id, group_id=group.id, name=name, icon=icon,
        kind="savings" if savings else "flexible",
    )
    db.add(category)
    db.flush()
    return category


def create_group(db: Session, user_id: str, name: str) -> CategoryGroup:
    name = name.strip()
    ensure_group_name_free(db, user_id, name)
    max_order = db.scalar(select(func.max(CategoryGroup.sort_order)).where(CategoryGroup.user_id == user_id))
    group = CategoryGroup(user_id=user_id, name=name, sort_order=(max_order or 0) + 1)
    db.add(group)
    db.flush()
    return group
