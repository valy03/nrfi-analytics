"""Team model (M3)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Team(Base, TimestampMixin):
    """An MLB club.

    ``id`` is the MLB Stats API team id (e.g. 147 = Yankees) rather than a
    surrogate key, so daily collection (M1) can reference teams directly.
    ``abbreviation`` is the join key for the Statcast backfill (M2), which
    identifies teams by code only ("NYY", "AZ", "ATH").
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    abbreviation: Mapped[str] = mapped_column(
        String(5), nullable=False, unique=True, index=True
    )
    team_code: Mapped[str | None] = mapped_column(String(5))
    league: Mapped[str | None] = mapped_column(String(30))
    division: Mapped[str | None] = mapped_column(String(40))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Team {self.abbreviation} ({self.id})>"
