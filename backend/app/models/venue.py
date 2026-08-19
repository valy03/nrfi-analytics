"""Venue model (M8.5): ballpark reference data for weather lookups.

Deliberately not foreign-keyed from ``games.venue_id``. The M2 Statcast
backfill covers spring-training and international-series venues outside
the ~30 current active parks, and retrofitting a hard FK onto ~18k
already-loaded games risks failing on exactly the rows this table was never
meant to cover. This is a lookup, not a constraint:
``app.collection.weather`` resolves what it can and skips a game cleanly
when its venue isn't in here.
"""

from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str | None] = mapped_column(String(80))
    # Plain float, not Numeric: coordinates don't need exact decimal
    # arithmetic, and a Decimal column reads back from Postgres as
    # decimal.Decimal — comparing that against the plain float the API
    # returns in app.ingestion.upsert's change-detection makes every
    # re-seed register as "updated" even when nothing changed, because a
    # float's binary value essentially never matches a Decimal's exact one.
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Venue {self.name} ({self.id})>"
