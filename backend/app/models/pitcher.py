"""Pitcher model (M3)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Pitcher(Base, TimestampMixin):
    """A pitcher, keyed by MLB Stats API person id.

    Only starters are populated today (they're what the probable-pitcher feed
    gives us), but nothing here is starter-specific — relievers can land in
    the same table when per-game stats arrive.
    """

    __tablename__ = "pitchers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    throws: Mapped[str | None] = mapped_column(String(1))  # "L" / "R"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Pitcher {self.full_name} ({self.id})>"
