from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import User
from app.security import BEARER, decode_access_token

DbDep = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], db: DbDep
) -> User:
    if credentials is None:
        raise AppError(401, "not_authenticated", "Sign in to continue", headers=BEARER)
    claims = decode_access_token(credentials.credentials)
    user = db.get(User, claims.user_id)
    if user is None:
        raise AppError(401, "invalid_token", "Invalid authentication token", headers=BEARER)
    return user


UserDep = Annotated[User, Depends(current_user)]
