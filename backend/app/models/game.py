"""Game model (M3) — the spine of the schema.

One row per MLB game, keyed by ``game_pk``. That key is shared by both data
sources (MLB Stats API and Statcast), which is what lets the daily feed (M1)
and the historical backfill (M2) write to the same row without a
reconciliation step: the daily loader fills in schedule/pitcher/venue fields,
the backfill fills in the first-inning outcome and NRFI label.

Outcome columns are nullable on purpose — a game that hasn't been played yet
has a schedule but no label, and that's exactly the row M7 predicts on.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import UtcDateTime
from app.models.pitcher import Pitcher
from app.models.team import Team


class Game(Base, TimestampMixin):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            "home_team_id <> away_team_id", name="teams_differ"
        ),
        Index("ix_games_season_date", "season", "game_date"),
    )

    # --- identity -------------------------------------------------------
    game_pk: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    game_date: Mapped[dt.date] = mapped_column(
        Date, nullable=False, index=True
    )
    season: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # "R" regular, "S" spring, "P"/"D"/"L"/"W" postseason.
    game_type: Mapped[str] = mapped_column(
        String(2), nullable=False, default="R", server_default="R"
    )
    status: Mapped[str | None] = mapped_column(String(40))

    # --- matchup --------------------------------------------------------
    away_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    venue_id: Mapped[int | None] = mapped_column(Integer)
    venue_name: Mapped[str | None] = mapped_column(String(80))
    start_time_utc: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)
    doubleheader: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    game_num: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    # --- probable starters (null until MLB announces them) --------------
    away_probable_pitcher_id: Mapped[int | None] = mapped_column(
        ForeignKey("pitchers.id")
    )
    home_probable_pitcher_id: Mapped[int | None] = mapped_column(
        ForeignKey("pitchers.id")
    )

    # --- outcome (null until the game is played) ------------------------
    away_score: Mapped[int | None] = mapped_column(Integer)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_runs_1st: Mapped[int | None] = mapped_column(Integer)
    home_runs_1st: Mapped[int | None] = mapped_column(Integer)
    first_inning_runs: Mapped[int | None] = mapped_column(Integer)
    nrfi: Mapped[bool | None] = mapped_column(Boolean, index=True)

    # --- weather (M8.5) — one snapshot, captured alongside the M7 job;
    # display-only per research.md, so "latest reading" is all this needs
    # rather than a history of readings. Null until a game both has a venue
    # app.collection.weather recognizes and has actually been collected.
    # Float, not Numeric — see app/models/venue.py's latitude/longitude
    # comment: a Decimal column defeats app.ingestion.upsert's
    # changed-vs-unchanged comparison against the plain floats the API
    # returns, and this is written through that same upsert path.
    weather_temp_f: Mapped[float | None] = mapped_column(Float)
    weather_conditions: Mapped[str | None] = mapped_column(String(60))
    weather_wind_mph: Mapped[float | None] = mapped_column(Float)
    weather_wind_direction_deg: Mapped[int | None] = mapped_column(Integer)
    weather_captured_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)

    # --- odds (M8.5) — moneyline only, display-only per research.md, not a
    # model input. One bookmaker's line, captured once a day.
    home_moneyline: Mapped[int | None] = mapped_column(Integer)
    away_moneyline: Mapped[int | None] = mapped_column(Integer)
    odds_bookmaker: Mapped[str | None] = mapped_column(String(40))
    odds_captured_at: Mapped[dt.datetime | None] = mapped_column(UtcDateTime)

    # --- relationships --------------------------------------------------
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_probable_pitcher: Mapped[Pitcher | None] = relationship(
        foreign_keys=[away_probable_pitcher_id]
    )
    home_probable_pitcher: Mapped[Pitcher | None] = relationship(
        foreign_keys=[home_probable_pitcher_id]
    )
    pitcher_stats: Mapped[list["PitcherGameStats"]] = relationship(  # noqa: F821
        back_populates="game", cascade="all, delete-orphan"
    )
    team_stats: Mapped[list["TeamGameStats"]] = relationship(  # noqa: F821
        back_populates="game", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(  # noqa: F821
        back_populates="game", cascade="all, delete-orphan"
    )

    @property
    def is_labeled(self) -> bool:
        """True once the first-inning outcome is known."""
        return self.nrfi is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Game {self.game_pk} {self.game_date} ({self.status})>"
