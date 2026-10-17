"""Grouped category tree and its management (spec: categories-api).

Archiving is the only retire path (design D1): transactions and budget
assignments reference categories, so nothing is ever hard-deleted. Groups
delete only when empty (design D2) — archived members count.

Credit cards' payment categories and their "Tarjetas de crédito" system
group are managed by the accounts API (they follow the card's rename and
archive): category CRUD may not archive, re-parent or delete them, nor put
other categories into the system group (409 `payment_category_locked`).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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
    SimilarGroup,
    SimilarMatch,
    SimilarView,
)
from ..services import categories as categories_service
from ..services import category_matching as matching

router = APIRouter(prefix="/categories", tags=["categories"])


def locked() -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "payment_category_locked"})


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


def _http(error: categories_service.CategoryError) -> HTTPException:
    return HTTPException(status_code=error.status, detail={"code": error.code})


def get_group_or_404(db: Session, user_id: str, group_id: str) -> CategoryGroup:
    try:
        return categories_service.get_group(db, user_id, group_id)
    except categories_service.CategoryError as error:
        raise _http(error) from error


def ensure_name_free_in_group(
    db: Session, user_id: str, group_id: str, name: str, exclude_id: str | None = None
) -> None:
    try:
        categories_service.ensure_name_free_in_group(db, user_id, group_id, name, exclude_id)
    except categories_service.CategoryError as error:
        raise _http(error) from error


def ensure_group_name_free(
    db: Session, user_id: str, name: str, exclude_id: str | None = None
) -> None:
    try:
        categories_service.ensure_group_name_free(db, user_id, name, exclude_id)
    except categories_service.CategoryError as error:
        raise _http(error) from error


@router.get("/similar", response_model=SimilarView)
def similar(
    name: str = Query(max_length=120),
    kind: Literal["category", "group"] = "category",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SimilarView:
    """Categories (or groups) that look like `name` (spec: category-matching):
    what to offer before creating a new one."""
    if not name.strip():
        raise HTTPException(status_code=422, detail={"code": "name_required"})
    if kind == "group":
        matches = matching.similar_groups(db, user, name)
        return SimilarView(matches=[SimilarMatch(id=m.id, name=m.name, reason=m.reason) for m in matches])
    matches = matching.similar_categories(db, user, name)
    group = matching.suggest_group(db, user, name, matches)
    return SimilarView(
        matches=[SimilarMatch(id=m.id, name=m.name, reason=m.reason, group_id=m.group_id, group_name=m.group_name)
                 for m in matches],
        suggested_group=SimilarGroup(id=group.id, name=group.name) if group else None,
    )


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Category:
    try:
        return categories_service.create_category(
            db, user.id, payload.group_id, payload.name, payload.icon, payload.savings
        )
    except categories_service.CategoryError as error:
        raise _http(error) from error


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
        target = get_group_or_404(db, user.id, payload.group_id)
        if target.id != category.group_id and (category.payment_account_id or target.system):
            raise locked()
        target_group_id = target.id
    if category.payment_account_id and payload.archived is not None:
        if payload.archived != category.archived:
            raise locked()

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
    try:
        return categories_service.create_group(db, user.id, payload.name)
    except categories_service.CategoryError as error:
        raise _http(error) from error


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
    if group.system:
        raise locked()
    # Archived members count: the group must be truly empty (design D2).
    member = db.scalar(select(Category).where(Category.group_id == group.id))
    if member is not None:
        raise HTTPException(status_code=409, detail={"code": "group_not_empty"})
    db.delete(group)
    db.flush()
