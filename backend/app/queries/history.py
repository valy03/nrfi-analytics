"""Historical-results queries (M8): past predictions and accuracy.

Both read from ``predictions`` left-joined to ``prediction_results`` — a
prediction whose game hasn't finished (or hasn't been graded yet;
app.grading.results runs separately) shows up with a null actual outcome
rather than being omitted. That's the honest state of an in-flight
prediction, not missing data. Accuracy, by contrast, only counts *graded*
predictions — an ungraded one isn't a win or a loss yet, so including it
either way would misstate the rate rather than just show fewer of them.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Game, Prediction, PredictionResult, Team
from app.schemas.history import AccuracyBucket, AccuracyReport, PredictionHistoryItem


def prediction_history(
    session: Session,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    team: str | None = None,
    model_version: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[PredictionHistoryItem]:
    query = (
        select(Prediction, PredictionResult, Game)
        .join(Game, Game.game_pk == Prediction.game_pk)
        .outerjoin(PredictionResult, PredictionResult.prediction_id == Prediction.id)
    )
    if start_date is not None:
        query = query.where(Game.game_date >= start_date)
    if end_date is not None:
        query = query.where(Game.game_date <= end_date)
    if model_version is not None:
        query = query.where(Prediction.model_version == model_version)
    if team:
        pattern = f"%{team.strip()}%"
        team_ids = list(
            session.scalars(
                select(Team.id).where(
                    Team.abbreviation.ilike(pattern) | Team.name.ilike(pattern)
                )
            )
        )
        query = query.where(
            Game.home_team_id.in_(team_ids) | Game.away_team_id.in_(team_ids)
        )
    query = (
        query.order_by(Game.game_date.desc(), Prediction.id.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = session.execute(query).all()
    if not rows:
        return []

    team_ids_needed = {g.home_team_id for _, _, g in rows} | {g.away_team_id for _, _, g in rows}
    teams = {t.id: t for t in session.scalars(select(Team).where(Team.id.in_(team_ids_needed)))}

    return [
        PredictionHistoryItem(
            game_pk=game.game_pk,
            game_date=game.game_date,
            home_team=teams[game.home_team_id].abbreviation,
            away_team=teams[game.away_team_id].abbreviation,
            predicted_label=prediction.predicted_label,
            actual_label=result.actual_label if result else None,
            correct=result.correct if result else None,
            confidence=prediction.confidence,
            nrfi_probability=prediction.nrfi_probability,
            model_name=prediction.model_name,
            model_version=prediction.model_version,
        )
        for prediction, result, game in rows
    ]


def _bucket(period: str, outcomes: list[bool]) -> AccuracyBucket:
    total = len(outcomes)
    correct = sum(outcomes)
    accuracy = (correct / total) if total else None
    return AccuracyBucket(
        period=period, total=total, correct=correct, accuracy=accuracy, win_rate=accuracy
    )


def accuracy_report(session: Session, model_version: str | None = None) -> AccuracyReport:
    """Overall / yearly / monthly accuracy over every graded prediction."""
    query = (
        select(Game.game_date, PredictionResult.correct)
        .join(Prediction, Prediction.id == PredictionResult.prediction_id)
        .join(Game, Game.game_pk == Prediction.game_pk)
    )
    if model_version is not None:
        query = query.where(Prediction.model_version == model_version)

    by_month: dict[str, list[bool]] = defaultdict(list)
    by_year: dict[str, list[bool]] = defaultdict(list)
    overall: list[bool] = []
    for game_date, correct in session.execute(query).all():
        outcome = bool(correct)
        overall.append(outcome)
        by_year[str(game_date.year)].append(outcome)
        by_month[f"{game_date.year:04d}-{game_date.month:02d}"].append(outcome)

    return AccuracyReport(
        overall=_bucket("overall", overall),
        monthly=[_bucket(k, v) for k, v in sorted(by_month.items())],
        yearly=[_bucket(k, v) for k, v in sorted(by_year.items())],
    )
