from datetime import timedelta

import jwt
import pytest
from sqlalchemy import select, update

from app.clock import utcnow
from app.config import settings
from app.models import RefreshToken, User
from app.routers.auth import COOKIE

SIGNUP = "/api/auth/signup"


def signup_body(**overrides):
    body = {"name": "Dana", "email": "dana@example.com", "password": "Password1"}
    return {**body, **overrides}


def refresh_with(client, raw):
    """Refresh using exactly this cookie value, ignoring whatever the client jar holds."""
    client.cookies.clear()
    return client.post("/api/auth/refresh", headers={"Cookie": f"{COOKIE}={raw}"})


def test_signup_returns_tokens_and_hashes_the_password(client, db):
    response = client.post(SIGNUP, json=signup_body())
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "dana@example.com"
    assert body["access_token"] and body["token_type"] == "bearer"

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api/auth" in cookie

    stored = db.scalar(select(User.password_hash).where(User.email == "dana@example.com"))
    assert stored.startswith("$argon2id$")
    assert "Password1" not in stored


@pytest.mark.parametrize(
    ("overrides", "field", "message"),
    [
        ({"email": "not-an-email"}, "email", "Enter a valid email address"),
        ({"password": "short1"}, "password", "at least 8 characters"),
        ({"password": "onlyletters"}, "password", "one letter and one number"),
        ({"password": "12345678"}, "password", "one letter and one number"),
        ({"name": "   "}, "name", "Name is required"),
    ],
)
def test_signup_rejects_invalid_input_with_field_errors(client, overrides, field, message):
    response = client.post(SIGNUP, json=signup_body(**overrides))
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert message in body["fields"][field]


def test_signup_rejects_a_duplicate_email_case_insensitively(client):
    assert client.post(SIGNUP, json=signup_body()).status_code == 201
    response = client.post(SIGNUP, json=signup_body(email="DANA@Example.com"))
    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


def test_login_accepts_the_right_password_and_rejects_the_rest(client):
    client.post(SIGNUP, json=signup_body())
    ok = client.post("/api/auth/login", json={"email": "dana@example.com", "password": "Password1"})
    assert ok.status_code == 200 and ok.json()["access_token"]

    wrong = client.post("/api/auth/login", json={"email": "dana@example.com", "password": "Nope12345"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "Password1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Invalid email or password"


def test_protected_endpoints_return_401_without_a_valid_token(client, alice):
    assert client.get("/api/auth/me").json()["code"] == "not_authenticated"
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).json()["code"] == "invalid_token"
    assert alice.get("/auth/me").json()["email"] == "alice@example.com"


def test_an_expired_access_token_returns_401_token_expired(client, alice):
    expired = jwt.encode(
        {"sub": alice.id, "type": "access", "exp": utcnow() - timedelta(seconds=5)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


def test_a_refresh_token_cannot_be_used_as_an_access_token(client, alice):
    forged = jwt.encode({"sub": alice.id, "type": "refresh", "exp": utcnow() + timedelta(hours=1)},
                        settings.jwt_secret, algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_refresh_rotates_the_token_and_issues_a_new_access_token(client):
    first = client.post(SIGNUP, json=signup_body())
    old_raw = first.cookies.get(COOKIE)

    second = refresh_with(client, old_raw)
    assert second.status_code == 200
    new_raw = second.cookies.get(COOKIE)
    assert new_raw and new_raw != old_raw

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"})
    assert me.status_code == 200


def test_refresh_without_a_cookie_is_401(client):
    client.cookies.clear()
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401


def test_two_tabs_refreshing_at_once_are_both_served(client):
    old_raw = client.post(SIGNUP, json=signup_body()).cookies.get(COOKIE)
    assert refresh_with(client, old_raw).status_code == 200
    assert refresh_with(client, old_raw).status_code == 200  # inside the grace window


def test_replaying_a_rotated_token_after_the_grace_window_ends_the_whole_login(client, db):
    old_raw = client.post(SIGNUP, json=signup_body()).cookies.get(COOKIE)
    new_raw = refresh_with(client, old_raw).cookies.get(COOKIE)

    stale = utcnow() - timedelta(seconds=settings.refresh_reuse_grace_seconds + 30)
    db.execute(update(RefreshToken).where(RefreshToken.rotated_at.is_not(None)).values(rotated_at=stale))
    db.commit()

    replay = refresh_with(client, old_raw)
    assert replay.status_code == 401 and replay.json()["code"] == "token_reuse"
    # the legitimate newer token is dead too: the family was revoked
    assert refresh_with(client, new_raw).status_code == 401


def test_logout_revokes_the_refresh_token(client):
    raw = client.post(SIGNUP, json=signup_body()).cookies.get(COOKIE)
    client.cookies.clear()
    out = client.post("/api/auth/logout", headers={"Cookie": f"{COOKIE}={raw}"})
    assert out.status_code == 204
    assert refresh_with(client, raw).status_code == 401
