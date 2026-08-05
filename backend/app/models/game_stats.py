"""Per-game box-score tables (M3).

These hold *observed* per-game numbers — the raw material M4 aggregates into
features (season/career NRFI%, first-inning ERA, team first-inning scoring
rate, and so on). Nothing derived or rolled-up lives here; that belongs to
the feature pipeline.

Every stat column is nullable because sources fill them in at different
times: the first-inning slice is available from the linescore right after the
1st, full-game lines only once the game ends.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.game import Game
from app.models.pitcher import Pitcher
from app.models.team import Team


class PitcherGameStats(Base, TimestampMixin):
    """One pitcher's line in one game, with the first inning broken out."""

    __tablename__ = "pitcher_game_stats"
    __table_args__ = (
        UniqueConstraint("game_pk", "pitcher_id", name="uq_pitcher_per_game"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_pk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.game_pk", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pitcher_id: Mapped[int] = mapped_column(
        ForeignKey("pitchers.id"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_starter: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # First inning only — the NRFI-relevant slice.
    batters_faced_1st: Mapped[int | None] = mapped_column(Integer)
    hits_1st: Mapped[int | None] = mapped_column(Integer)
    runs_1st: Mapped[int | None] = mapped_column(Integer)
    earned_runs_1st: Mapped[int | None] = mapped_column(Integer)
    walks_1st: Mapped[int | None] = mapped_column(Integer)
    strikeouts_1st: Mapped[int | None] = mapped_column(Integer)
    home_runs_1st: Mapped[int | None] = mapped_column(Integer)
    pitches_1st: Mapped[int | None] = mapped_column(Integer)

    # Full outing.
    innings_pitched: Mapped[float | None] = mapped_column(Numeric(4, 1))
    batters_faced: Mapped[int | None] = mapped_column(Integer)
    hits: Mapped[int | None] = mapped_column(Integer)
    runs: Mapped[int | None] = mapped_column(Integer)
    earned_runs: Mapped[int | None] = mapped_column(Integer)
    walks: Mapped[int | None] = mapped_column(Integer)
    strikeouts: Mapped[int | None] = mapped_column(Integer)
    home_runs: Mapped[int | None] = mapped_column(Integer)
    pitches: Mapped[int | None] = mapped_column(Integer)

    game: Mapped[Game] = relationship(back_populates="pitcher_stats")
    pitcher: Mapped[Pitcher] = relationship()
    team: Mapped[Team] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PitcherGameStats g={self.game_pk} p={self.pitcher_id}>"


class TeamGameStats(Base, TimestampMixin):
    """One team's offensive line in one game, first inning broken out."""

    __tablename__ = "team_game_stats"
    __table_args__ = (
        UniqueConstraint("game_pk", "team_id", name="uq_team_per_game"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_pk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.game_pk", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # First inning only.
    runs_1st: Mapped[int | None] = mapped_column(Integer)
    hits_1st: Mapped[int | None] = mapped_column(Integer)
    walks_1st: Mapped[int | None] = mapped_column(Integer)
    strikeouts_1st: Mapped[int | None] = mapped_column(Integer)
    batters_1st: Mapped[int | None] = mapped_column(Integer)
    left_on_base_1st: Mapped[int | None] = mapped_column(Integer)

    # Full game.
    runs: Mapped[int | None] = mapped_column(Integer)
    hits: Mapped[int | None] = mapped_column(Integer)
    walks: Mapped[int | None] = mapped_column(Integer)
    strikeouts: Mapped[int | None] = mapped_column(Integer)
    home_runs: Mapped[int | None] = mapped_column(Integer)
    left_on_base: Mapped[int | None] = mapped_column(Integer)

    game: Mapped[Game] = relationship(back_populates="team_stats")
    team: Mapped[Team] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TeamGameStats g={self.game_pk} t={self.team_id}>"
