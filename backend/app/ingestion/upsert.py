"""Idempotent bulk upsert (M3).

Both loaders re-run over overlapping date ranges constantly (a daily job
re-reads today's slate every few hours; a backfill gets re-run with a wider
window), so "insert or update, never duplicate" is the core requirement —
it's literally the M3 exit criterion.

This is deliberately written with plain SELECT + bulk INSERT/UPDATE instead
of Postgres' ``ON CONFLICT``. Two reasons: it stays dialect-agnostic (the
test suite runs on in-memory SQLite, no live database needed), and it can
report inserted/updated counts, which the CLIs print so a re-run visibly
does nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.db.base import Base

# Keep IN (...) / OR (...) lists to a sane size regardless of batch size.
LOOKUP_CHUNK = 1000


@dataclass(frozen=True)
class UpsertCounts:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.skipped

    def __add__(self, other: "UpsertCounts") -> "UpsertCounts":
        return UpsertCounts(
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            skipped=self.skipped + other.skipped,
        )

    def __str__(self) -> str:
        return (
            f"{self.inserted} inserted, {self.updated} updated, "
            f"{self.skipped} unchanged"
        )


def upsert_rows(
    session: Session,
    model: type[Base],
    rows: Iterable[dict[str, Any]],
    key_cols: Sequence[str],
    update_cols: Sequence[str] | None = None,
    skip_none_updates: bool = True,
) -> UpsertCounts:
    """Insert new rows and update existing ones, matched on ``key_cols``.

    ``update_cols`` defaults to every non-key column present in the payload.
    With ``skip_none_updates`` (the default) a ``None`` value never
    overwrites a stored value — this is what lets the two loaders share the
    ``games`` table: the daily feed doesn't know first-inning runs and the
    Statcast backfill doesn't know the venue, and neither should blank out
    what the other wrote.

    Rows are deduped within the batch (last one wins) so a caller passing the
    same key twice can't trip a unique constraint.
    """
    batch = {_key_of(r, key_cols): r for r in rows}
    if not batch:
        return UpsertCounts()

    existing = _load_existing(session, model, key_cols, list(batch))

    to_insert: list[dict[str, Any]] = []
    inserted = updated = skipped = 0

    for key, row in batch.items():
        current = existing.get(key)
        if current is None:
            to_insert.append(row)
            inserted += 1
            continue

        columns = update_cols or [c for c in row if c not in key_cols]
        changed = False
        for col in columns:
            if col in key_cols or col not in row:
                continue
            value = row[col]
            if value is None and skip_none_updates:
                continue
            if getattr(current, col) != value:
                setattr(current, col, value)
                changed = True
        updated += changed
        skipped += not changed

    if to_insert:
        # executemany needs a uniform key set across rows; a caller that
        # omits an optional column on some rows shouldn't have to care.
        all_cols = {col for row in to_insert for col in row}
        session.execute(
            model.__table__.insert(),
            [{col: row.get(col) for col in all_cols} for row in to_insert],
        )

    session.flush()
    return UpsertCounts(inserted=inserted, updated=updated, skipped=skipped)


def _key_of(row: dict[str, Any], key_cols: Sequence[str]) -> tuple:
    return tuple(row[col] for col in key_cols)


def _load_existing(
    session: Session,
    model: type[Base],
    key_cols: Sequence[str],
    keys: list[tuple],
) -> dict[tuple, Base]:
    """Fetch already-stored rows for ``keys``, chunked to bound query size."""
    found: dict[tuple, Base] = {}
    for start in range(0, len(keys), LOOKUP_CHUNK):
        chunk = keys[start : start + LOOKUP_CHUNK]
        for obj in session.scalars(
            select(model).where(_key_filter(model, key_cols, chunk))
        ):
            found[tuple(getattr(obj, col) for col in key_cols)] = obj
    return found


def _key_filter(model: type[Base], key_cols: Sequence[str], keys: list[tuple]):
    """Build a WHERE that matches any of ``keys`` (single- or composite).

    Composite keys use a row-value ``IN`` — one comparison per key instead of
    an OR of ANDs, which matters once a batch runs to thousands of rows.
    """
    if len(key_cols) == 1:
        return getattr(model, key_cols[0]).in_([k[0] for k in keys])

    return tuple_(*(getattr(model, col) for col in key_cols)).in_(keys)
