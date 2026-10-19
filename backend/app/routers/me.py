"""Who is signed in (spec: authentication)."""

from fastapi import APIRouter, Depends

from ..deps import current_user
from ..models import User
from ..schemas import MeOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
def get_me(user: User = Depends(current_user)) -> User:
    return user
