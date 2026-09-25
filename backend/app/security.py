import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.clock import utcnow
from app.config import settings
from app.errors import AppError

ALGORITHM = "HS256"
BEARER = {"WWW-Authenticate": "Bearer"}

hasher = PasswordHasher()  # argon2id with the library's defaults
# Verified against when an email is unknown, so "no such user" and "wrong password"
# cost the same and can't be told apart by timing.
_DUMMY_HASH = hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_verify(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


@dataclass(frozen=True)
class Claims:
    user_id: uuid.UUID
    exp: int


def create_access_token(user_id: uuid.UUID) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Claims:
    try:
        data = jwt.decode(
            token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "type"]}
        )
        if data["type"] != "access":
            raise jwt.InvalidTokenError("not an access token")
        return Claims(user_id=uuid.UUID(data["sub"]), exp=int(data["exp"]))
    except jwt.ExpiredSignatureError:
        raise AppError(401, "token_expired", "Your session has expired", headers=BEARER) from None
    except (jwt.InvalidTokenError, ValueError):
        raise AppError(401, "invalid_token", "Invalid authentication token", headers=BEARER) from None


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw value for the cookie, hash for the database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)
