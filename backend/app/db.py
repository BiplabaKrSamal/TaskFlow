from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)


def get_db() -> Iterator[Session]:
    # Nothing is committed implicitly: routes commit on success, and closing the
    # session rolls back anything left over when a request fails half way.
    with SessionLocal() as session:
        yield session
