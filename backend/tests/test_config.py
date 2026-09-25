import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # Managed providers (Render, Heroku, ...) hand out a bare scheme with no driver.
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        # Already explicit: passed through unchanged, not double-prefixed.
        ("postgresql+psycopg://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
    ],
)
def test_database_url_gets_the_psycopg_driver_named(given, expected):
    assert Settings(database_url=given, jwt_secret="x" * 32).database_url == expected
