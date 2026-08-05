"""Custom column types (M3)."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):
    """A timestamp that is always timezone-aware UTC in Python.

    Postgres ``timestamptz`` already round-trips an aware datetime, but
    SQLite silently drops the tzinfo — so the same code would read back an
    aware value in production and a naive one in tests, and any comparison
    between the two raises or (worse) reports a spurious difference. That
    second failure mode is the dangerous one here: the ingestion upsert
    decides "changed or unchanged" by comparing stored values to incoming
    ones, so a naive/aware mismatch would make every re-run report updates
    it didn't make.

    Naive input is assumed to be UTC rather than rejected — the MLB feed's
    timestamps are UTC by construction.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: dt.datetime | None, dialect
    ) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)

    def process_result_value(
        self, value: dt.datetime | None, dialect
    ) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)
