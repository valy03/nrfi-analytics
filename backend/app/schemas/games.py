"""Response schemas for the games endpoints (M8, M8.5).

Traditional pitcher/team stats (``era``, ``whip``, ``fip``, ``xera``,
``ops``, ``obp``, ``slg``, ``batting_avg``) are still typed but always
``None`` — no data source for those exists yet (docs/milestones.md M8).
``weather`` and ``odds`` *are* real now (M8.5): populated from
``app.prediction.enrich``'s captures whenever a game has them, and still
``None`` for a game that hasn't been enriched yet (no venue match, no
posted line, or simply not captured yet) — same "present in the contract,
honestly empty until there's real data" approach M8 established.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class TeamOut(BaseModel):
    id: int
    name: str
    abbreviation: str


class WeatherOut(BaseModel):
    temp_f: float
    conditions: str
    wind_mph: float
    wind_direction_deg: int | None = None
    captured_at: dt.datetime


class OddsOut(BaseModel):
    home_moneyline: int
    away_moneyline: int
    bookmaker: str
    captured_at: dt.datetime


class PitcherRecentStart(BaseModel):
    """One of a starter's most recent outings, strictly before the game
    being described — the same as-of cutoff the M4 feature pipeline uses,
    so this never shows a start that hadn't happened yet at prediction time.
    """

    game_pk: int
    game_date: dt.date
    opponent: str
    runs_1st: int | None
    nrfi: bool | None


class PitcherOut(BaseModel):
    id: int
    full_name: str
    throws: str | None = None

    # Traditional season stats — no data source yet (M8 fast-follow).
    era: float | None = None
    whip: float | None = None
    fip: float | None = None
    xera: float | None = None

    # First-inning rate stats, as of this game — sourced from the stored
    # prediction's feature snapshot when one exists, so these are exactly
    # what the model saw, not a live recomputation that could drift from it.
    k_rate_1st: float | None = None
    bb_rate_1st: float | None = None
    nrfi_rate_career: float | None = None
    nrfi_rate_season: float | None = None
    nrfi_rate_last5: float | None = None
    starts_prior: int | None = None

    recent_starts: list[PitcherRecentStart] = []


class TeamStatsOut(BaseModel):
    """A team's first-inning offensive profile as of this game."""

    scored_1st_rate: float | None = None
    scored_1st_rate_season: float | None = None
    scored_1st_rate_recent: float | None = None
    scored_1st_rate_split: float | None = None  # home/away split
    runs_1st_avg: float | None = None
    k_rate_1st: float | None = None
    games_prior: int | None = None

    # Traditional stats — no data source yet (M8 fast-follow).
    ops: float | None = None
    obp: float | None = None
    slg: float | None = None
    batting_avg: float | None = None


class PredictionOut(BaseModel):
    predicted_label: str
    nrfi_probability: float
    yrfi_probability: float
    confidence: float
    model_name: str
    model_version: str
    predicted_at: dt.datetime


class ActualResultOut(BaseModel):
    """The real outcome, once the game's been played."""

    home_runs_1st: int | None
    away_runs_1st: int | None
    first_inning_runs: int | None
    nrfi: bool | None
    home_score: int | None
    away_score: int | None


class GameSummary(BaseModel):
    """One row of the dashboard's today's-games list."""

    game_pk: int
    game_date: dt.date
    start_time_utc: dt.datetime | None
    status: str | None
    venue_name: str | None
    home_team: TeamOut
    away_team: TeamOut
    home_pitcher: PitcherOut | None
    away_pitcher: PitcherOut | None
    prediction: PredictionOut | None
    correct: bool | None = None
    actual_result: ActualResultOut | None = None
    weather: WeatherOut | None = None


class GameDetail(BaseModel):
    """The full game-detail page."""

    game_pk: int
    game_date: dt.date
    start_time_utc: dt.datetime | None
    status: str | None
    venue_name: str | None
    home_team: TeamOut
    away_team: TeamOut
    home_pitcher: PitcherOut | None
    away_pitcher: PitcherOut | None
    home_team_stats: TeamStatsOut | None
    away_team_stats: TeamStatsOut | None
    prediction: PredictionOut | None
    correct: bool | None = None
    explanation: list[str] = []
    actual_result: ActualResultOut | None = None
    weather: WeatherOut | None = None
    odds: OddsOut | None = None
