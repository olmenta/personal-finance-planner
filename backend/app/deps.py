"""Shared FastAPI dependencies.

`current_user` is the person behind the request (spec: authentication):
in `auth0` mode, from the Bearer token the BFF forwards; in `dev_user` mode
(local and test only), the seeded development user. Every query filters by
the returned user's id.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import AuthUnavailable, Unauthenticated, verify
from .config import get_settings
from .db import get_db
from .models import User
from .seed import get_dev_user
from .services import users


def _unauthenticated() -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "unauthenticated"},
                         headers={"WWW-Authenticate": "Bearer"})


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    if get_settings().auth_mode == "dev_user":
        user = get_dev_user(db)
        if user is None:
            raise HTTPException(status_code=503, detail={"code": "dev_user_not_seeded"})
        return user
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthenticated()
    try:
        identity = verify(token)
    except Unauthenticated as error:
        raise _unauthenticated() from error
    except AuthUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "auth_unavailable"}) from error
    return users.resolve(db, identity.sub, identity.email)
