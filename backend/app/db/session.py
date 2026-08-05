"""Engine and session factory (M3).

The engine is created lazily so that importing ``app.db`` never tries to
reach Postgres — useful for tests and for the collection CLIs (M1/M2), which
don't need a database at all.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Process-wide engine, built from ``DATABASE_URL``."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,  # survive Postgres dropping idle connections
        future=True,
    )


@lru_cache
def _get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )


def SessionLocal(**kwargs) -> Session:  # noqa: N802 - conventional name
    """Open a new Session bound to the shared engine."""
    return _get_sessionmaker()(**kwargs)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on failure."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency (used from M8 onward)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
