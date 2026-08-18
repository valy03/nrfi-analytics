"""Analytics queries (M8): leaderboards and frequency charts.

All aggregates over data other milestones already populate in full —
``games``/``pitcher_game_stats``/``team_game_stats`` cover the whole
2018-present history (M2/M3/M4), so these charts are dense from day one,
unlike the accuracy/model-performance views in app.queries.history which
only fill in as M7 actually runs.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    Game,
    Pitcher,
    PitcherGameStats,
    Prediction,
    PredictionResult,
    Team,
    TeamGameStats,
)
from app.schemas.analytics import (
    ModelPerformanceEntry,
    NrfiFrequencyPoint,
    PitcherLeaderboardEntry,
    TeamLeaderboardEntry,
)


def nrfi_frequency(session: Session) -> list[NrfiFrequencyPoint]:
    """NRFI rate per season, across every labeled regular-season game."""
    rows = session.execute(
        select(
            Game.season,
            func.count().label("games"),
            func.avg(case((Game.nrfi.is_(True), 1.0), else_=0.0)).label("nrfi_rate"),
        )
        .where(Game.nrfi.is_not(None), Game.game_type == "R")
        .group_by(Game.season)
        .order_by(Game.season)
    ).all()
    return [
        NrfiFrequencyPoint(period=str(season), games=games, nrfi_rate=float(rate))
        for season, games, rate in rows
    ]


def pitcher_leaderboard(
    session: Session, min_starts: int = 10, limit: int = 20
) -> list[PitcherLeaderboardEntry]:
    """Starters ranked by observed first-inning NRFI rate, highest first.

    A minimum-starts floor keeps one clean outing from outranking a
    season's worth of evidence — the same small-sample concern
    app.features.shrinkage exists to handle for the model, just a plain
    floor here since this is descriptive, not predictive.
    """
    nrfi_rate = func.avg(case((PitcherGameStats.runs_1st == 0, 1.0), else_=0.0))
    rows = session.execute(
        select(
            PitcherGameStats.pitcher_id,
            Pitcher.full_name,
            func.count().label("starts"),
            nrfi_rate.label("nrfi_rate"),
            func.avg(PitcherGameStats.runs_1st * 1.0).label("runs_1st_avg"),
        )
        .join(Pitcher, Pitcher.id == PitcherGameStats.pitcher_id)
        .where(
            PitcherGameStats.is_starter.is_(True),
            PitcherGameStats.runs_1st.is_not(None),
        )
        .group_by(PitcherGameStats.pitcher_id, Pitcher.full_name)
        .having(func.count() >= min_starts)
        .order_by(nrfi_rate.desc())
        .limit(limit)
    ).all()
    return [
        PitcherLeaderboardEntry(
            pitcher_id=pid,
            full_name=name,
            starts=starts,
            nrfi_rate=float(rate),
            runs_1st_avg=float(runs_avg),
        )
        for pid, name, starts, rate, runs_avg in rows
    ]


def team_leaderboard(
    session: Session, min_games: int = 10, limit: int = 20
) -> list[TeamLeaderboardEntry]:
    """Teams ranked by first-inning scoring rate, quietest offense first —
    the direction that favors NRFI, matching what this app actually
    predicts.
    """
    scored_rate = func.avg(case((TeamGameStats.runs_1st > 0, 1.0), else_=0.0))
    rows = session.execute(
        select(
            TeamGameStats.team_id,
            Team.abbreviation,
            func.count().label("games"),
            scored_rate.label("scored_1st_rate"),
        )
        .join(Team, Team.id == TeamGameStats.team_id)
        .where(TeamGameStats.runs_1st.is_not(None))
        .group_by(TeamGameStats.team_id, Team.abbreviation)
        .having(func.count() >= min_games)
        .order_by(scored_rate)
        .limit(limit)
    ).all()
    return [
        TeamLeaderboardEntry(team_id=tid, abbreviation=abbr, games=games, scored_1st_rate=float(rate))
        for tid, abbr, games, rate in rows
    ]


def model_performance(session: Session) -> list[ModelPerformanceEntry]:
    """Graded accuracy per (model_name, model_version) — the real substance
    behind M6's "which model wins" story, tracked as new champions ship.
    """
    rows = session.execute(
        select(
            Prediction.model_name,
            Prediction.model_version,
            func.count().label("total"),
            func.sum(case((PredictionResult.correct.is_(True), 1), else_=0)).label("correct"),
        )
        .join(PredictionResult, PredictionResult.prediction_id == Prediction.id)
        .group_by(Prediction.model_name, Prediction.model_version)
        .order_by(Prediction.model_version)
    ).all()
    return [
        ModelPerformanceEntry(
            model_name=name,
            model_version=version,
            total=total,
            correct=correct,
            accuracy=(correct / total) if total else 0.0,
        )
        for name, version, total, correct in rows
    ]
