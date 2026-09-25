import os
import signal
from dataclasses import dataclass
from pathlib import Path

# Settings are read at import time, so the test environment is set up first.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://taskflow:taskflow@localhost:5432/taskflow_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-1234"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _ensure_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("select 1 from pg_database where datname = :name"), {"name": url.database})
        if not exists:
            conn.execute(text(f'create database "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    """A fresh schema built by the real migrations, so the migrations are tested too."""
    from app import security
    from app.db import engine

    security.hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)  # keep signups fast
    _ensure_database()
    with engine.begin() as conn:
        conn.execute(text("drop schema public cascade"))
        conn.execute(text("create schema public"))
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(database):
    from app.db import engine

    with engine.begin() as conn:
        conn.execute(
            text(
                "truncate refresh_tokens, activity_log, comments, tasks, project_members, projects, users "
                "restart identity cascade"
            )
        )


@pytest.fixture()
def client():
    from app.main import app

    # Used as a context manager so requests and websockets share one event loop.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    from app.db import SessionLocal

    with SessionLocal() as session:
        yield session


@dataclass
class Person:
    client: TestClient
    id: str
    name: str
    email: str
    token: str

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def request(self, method: str, path: str, **kwargs):
        return self.client.request(method, f"/api{path}", headers=self.headers, **kwargs)

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs):
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self.request("DELETE", path, **kwargs)


@pytest.fixture()
def make_user(client):
    def make(name: str) -> Person:
        email = f"{name.lower()}@example.com"
        response = client.post("/api/auth/signup", json={"name": name, "email": email, "password": "Password1"})
        assert response.status_code == 201, response.text
        client.cookies.clear()
        body = response.json()
        return Person(client, body["user"]["id"], name, email, body["access_token"])

    return make


@pytest.fixture()
def alice(make_user):
    return make_user("Alice")


@pytest.fixture()
def bob(make_user):
    return make_user("Bob")


@pytest.fixture()
def carol(make_user):
    return make_user("Carol")


@pytest.fixture(autouse=True)
def fail_instead_of_hanging():
    def give_up(*_):
        raise TimeoutError("test ran longer than 30s; a websocket read is probably waiting for a message that never came")

    signal.signal(signal.SIGALRM, give_up)
    signal.alarm(30)
    yield
    signal.alarm(0)
