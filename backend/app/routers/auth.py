from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.config import settings
from app.deps import DbDep, UserDep
from app.errors import AppError, error_response
from app.models import User
from app.schemas.auth import AuthOut, LoginIn, SignupIn, UserOut
from app.security import (
    burn_verify,
    create_access_token,
    hash_password,
    verify_password,
)
from app.services import sessions

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE = "taskflow_refresh"
COOKIE_PATH = "/api/auth"


def _set_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        COOKIE,
        raw,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _auth_out(user: User) -> AuthOut:
    return AuthOut(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_ttl_seconds,
        user=UserOut.model_validate(user),
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=AuthOut)
def signup(payload: SignupIn, response: Response, db: DbDep):
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise AppError(
            409, "email_taken", "An account with this email already exists", fields={"email": "Email already in use"}
        )
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    raw = sessions.start_session(db, user)
    db.commit()
    _set_cookie(response, raw)
    return _auth_out(user)


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, response: Response, db: DbDep):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        burn_verify(payload.password)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    raw = sessions.start_session(db, user)
    db.commit()
    _set_cookie(response, raw)
    return _auth_out(user)


@router.post("/refresh", response_model=AuthOut)
def refresh(
    response: Response, db: DbDep, refresh_token: Annotated[str | None, Cookie(alias=COOKIE)] = None
):
    try:
        user, raw = sessions.rotate(db, refresh_token)
    except AppError as err:
        failed = error_response(err)
        failed.delete_cookie(COOKIE, path=COOKIE_PATH)
        return failed
    db.commit()
    _set_cookie(response, raw)
    return _auth_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbDep, refresh_token: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    sessions.end_session(db, refresh_token)
    db.commit()
    done = Response(status_code=status.HTTP_204_NO_CONTENT)
    done.delete_cookie(COOKIE, path=COOKIE_PATH)
    return done


@router.get("/me", response_model=UserOut)
def me(user: UserDep):
    return user
