"""Shared test fixtures.

The M3 ingestion tests run against an in-memory SQLite database rather than
the Docker Postgres: the loaders' logic (mapping, merging, idempotency) is
dialect-independent, and keeping the suite offline means `pytest` needs
nothing running. The schema itself is verified against real Postgres by the
Alembic migration (`alembic upgrade head` / `alembic check`).
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models import Base


@pytest.fixture
def session():
    """A fresh, fully-migrated in-memory database per test."""
    engine = create_engine("sqlite://")

    # SQLite ignores foreign keys unless asked — and FK enforcement is the
    # point of half these tests (teams must exist before games reference them).
    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()
