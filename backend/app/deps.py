"""Shared FastAPI dependencies.

Single seeded dev user for now; the Auth0 change replaces current_user with
JWT-derived identity without touching query logic (queries already filter by
user_id everywhere).
"""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .seed import get_dev_user


def current_user(db: Session = Depends(get_db)) -> User:
    user = get_dev_user(db)
    if user is None:
        raise HTTPException(status_code=503, detail={"code": "dev_user_not_seeded"})
    return user
