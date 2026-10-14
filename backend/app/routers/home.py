"""Home: one versioned snapshot of what to resolve now (spec: home)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import HomeView
from ..services.home import build_home

router = APIRouter(tags=["home"])


@router.get("/home", response_model=HomeView)
def get_home(db: Session = Depends(get_db), user: User = Depends(current_user)) -> HomeView:
    return build_home(db, user)
