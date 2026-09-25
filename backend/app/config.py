from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Later files win, so a backend/.env overrides the repo-level one.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow"
    jwt_secret: str
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 7 * 24 * 3600
    # A just-rotated refresh token is still accepted for this long, so two tabs
    # refreshing at the same moment don't look like token theft.
    refresh_reuse_grace_seconds: int = 10
    cookie_secure: bool = False
    ws_auth_timeout_seconds: float = 5.0
    ws_send_timeout_seconds: float = 5.0

    @field_validator("jwt_secret")
    @classmethod
    def _long_enough(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def _use_psycopg(cls, value: str) -> str:
        # Managed Postgres providers (Render, Heroku, ...) hand out a bare
        # postgres:// or postgresql:// URL. SQLAlchemy needs the driver named
        # explicitly, and this app is built on psycopg3, not the psycopg2 default.
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value


settings = Settings()
