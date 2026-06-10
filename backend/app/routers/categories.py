"""Grouped category tree."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import CategoryGroup, User
from ..schemas import CategoryGroupOut

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
