"""Grouped category tree and its management (spec: categories-api).

Archiving is the only retire path (design D1): transactions and budget
assignments reference categories, so nothing is ever hard-deleted. Groups
delete only when empty (design D2) — archived members count.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Category, CategoryGroup, User
from ..schemas import (
    CategoryCreate,
    CategoryGroupOut,
    CategoryOut,
    CategoryUpdate,
    GroupCreate,
    GroupUpdate,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryGroupOut])
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[CategoryGroup]:
    return list(
        db.scalars(
            select(CategoryGroup)
            .where(CategoryGroup.user_id == user.id)
            .order_by(CategoryGroup.sort_order)
        )
    )


def get_group_or_404(db: Session, user_id: str, group_id: str) -> CategoryGroup:
    group = db.scalar(
        select(CategoryGroup).where(
            CategoryGroup.id == group_id, CategoryGroup.user_id == user_id
        )
    )
    if group is None:
        raise HTTPException(status_code=404, detail={"code": "group_not_found"})
    return group


def ensure_name_free_in_group(
    db: Session, user_id: str, group_id: str, name: str, exclude_id: str | None = None
) -> None:
    """Per-group unique names, case-insensitive (design D3). Different groups
    may share a name ("Seguro" under Coche and Casa)."""
    query = select(Category).where(
        Category.user_id == user_id,
        Category.group_id == group_id,
        func.lower(Category.name) == name.lower(),
    )
    if exclude_id:
        query = query.where(Category.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail={"code": "category_exists"})


def ensure_group_name_free(
    db: Session, user_id: str, name: str, exclude_id: str | None = None
) -> None:
    query = select(CategoryGroup).where(
        CategoryGroup.user_id == user_id,
        func.lower(CategoryGroup.name) == name.lower(),
    )
    if exclude_id:
        query = query.where(CategoryGroup.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail={"code": "group_exists"})


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Category:
    group = get_group_or_404(db, user.id, payload.group_id)
    name = payload.name.strip()
    ensure_name_free_in_group(db, user.id, group.id, name)

    category = Category(
        user_id=user.id, group_id=group.id, name=name, icon=payload.icon,
        kind="savings" if payload.savings else "flexible",
    )
    db.add(category)
    db.flush()
    return category


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail={"code": "category_not_found"})

    target_group_id = category.group_id
    if payload.group_id is not None:
        target_group_id = get_group_or_404(db, user.id, payload.group_id).id

    if payload.name is not None or payload.group_id is not None:
        name = (payload.name or category.name).strip()
        ensure_name_free_in_group(db, user.id, target_group_id, name, exclude_id=category.id)
        category.name = name
        category.group_id = target_group_id

    if payload.icon is not None:
        category.icon = payload.icon
    if payload.archived is not None:
        category.archived = payload.archived
    if payload.savings is not None:
        category.kind = "savings" if payload.savings else "flexible"

    db.flush()
    return category


# ---- Groups -------------------------------------------------------------------


@router.post("/groups", response_model=CategoryGroupOut, status_code=201)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> CategoryGroup:
    name = payload.name.strip()
    ensure_group_name_free(db, user.id, name)
    max_order = db.scalar(
        select(func.max(CategoryGroup.sort_order)).where(CategoryGroup.user_id == user.id)
    )
    group = CategoryGroup(user_id=user.id, name=name, sort_order=(max_order or 0) + 1)
    db.add(group)
    db.flush()
    return group


@router.patch("/groups/{group_id}", response_model=CategoryGroupOut)
def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> CategoryGroup:
    group = get_group_or_404(db, user.id, group_id)
    if payload.name is not None:
        name = payload.name.strip()
        ensure_group_name_free(db, user.id, name, exclude_id=group.id)
        group.name = name
    if payload.sort_order is not None:
        group.sort_order = payload.sort_order
    db.flush()
    return group


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    group = get_group_or_404(db, user.id, group_id)
    # Archived members count: the group must be truly empty (design D2).
    member = db.scalar(select(Category).where(Category.group_id == group.id))
    if member is not None:
        raise HTTPException(status_code=409, detail={"code": "group_not_empty"})
    db.delete(group)
    db.flush()
