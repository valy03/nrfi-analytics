"""Shared test fixtures.

The M3 ingestion tests run against an in-memory SQLite database rather than
the Docker Postgres: the loaders' logic (mapping, merging, idempotency) is
dialect-independent, and keeping the suite offline means `pytest` needs
nothing running. The schema itself is verified against real Postgres by the
Alembic migration (`alembic upgrade head` / `alembic check`).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base


@pytest.fixture
def session():
    """A fresh, fully-migrated in-memory database per test.

    ``StaticPool`` + ``check_same_thread=False``: an in-memory SQLite
    database lives only on its one connection, and FastAPI's TestClient
    (M8) runs route handlers in a worker thread. Without a single shared
    connection, that thread would open a brand-new, empty in-memory
    database instead of reusing this one — "no such table" even though the
    test just created it.
    """
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # SQLite ignores foreign keys unless asked — and FK enforcement is the
    # point of half these tests (teams must exist before games reference them).
    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(session):
    """A FastAPI TestClient wired to the same in-memory session (M8) — seed
    rows through ``session`` directly, then hit the API and see them.
    """

    def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
