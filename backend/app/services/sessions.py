import uuid
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.clock import utcnow
from app.config import settings
from app.errors import AppError
from app.models import RefreshToken, User
from app.security import hash_refresh_token, new_refresh_token


def _purge_expired(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.expires_at < utcnow()))


def _issue(db: Session, user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    raw, digest = new_refresh_token()
    expires = utcnow() + timedelta(seconds=settings.refresh_token_ttl_seconds)
    db.add(RefreshToken(user_id=user_id, family_id=family_id, token_hash=digest, expires_at=expires))
    return raw


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def start_session(db: Session, user: User) -> str:
    """A login starts a new token family. Returns the raw refresh token for the cookie."""
    _purge_expired(db, user.id)
    return _issue(db, user.id, uuid.uuid4())


def rotate(db: Session, raw: str | None) -> tuple[User, str]:
    """Trade a refresh token for a new one. Each token works once (plus a short grace window)."""
    if not raw:
        raise AppError(401, "not_authenticated", "You are not signed in")

    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)).with_for_update()
    )
    if row is None:
        raise AppError(401, "invalid_refresh_token", "Your session is no longer valid. Sign in again.")

    now = utcnow()
    if row.revoked_at is not None or row.expires_at <= now:
        raise AppError(401, "session_expired", "Your session has expired. Sign in again.")

    if row.rotated_at is not None and (now - row.rotated_at).total_seconds() > settings.refresh_reuse_grace_seconds:
        # A token that was already traded in has come back after the grace window.
        # Either a thief or a stale copy is using it, so end the whole login.
        _revoke_family(db, row.family_id)
        db.commit()
        raise AppError(401, "token_reuse", "This session was signed out for your safety. Sign in again.")

    user = db.get(User, row.user_id)
    if row.rotated_at is None:
        row.rotated_at = now
    new_raw = _issue(db, row.user_id, row.family_id)
    _purge_expired(db, row.user_id)
    return user, new_raw


def end_session(db: Session, raw: str | None) -> None:
    if not raw:
        return
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    if row is not None:
        _revoke_family(db, row.family_id)
