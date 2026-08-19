"""Games queries (M8): today's slate and single-game detail.

Read-only — the building blocks behind app.routers.games. Nothing here
writes to the database or calls out to any API; that's M1/M7's job. If a
day's schedule hasn't been refreshed or predicted yet, these simply return
whatever's already stored, same as any other read path.

Pitcher/team rate stats and the prediction explanation are sourced from the
*stored prediction's* feature snapshot when one exists, not recomputed live.
That's deliberate: it's what Prediction.features exists for (see
app/models/prediction.py) — a game's numbers stay exactly what the model
actually saw, and a game with no prediction yet (no announced starters,
already played before M7 existed) honestly shows no rate stats rather than
a live recomputation that could quietly drift from what was predicted.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Game, Pitcher, PitcherGameStats, Prediction, Team
from app.prediction.infer import ChampionNotFoundError, champion_identity
from app.queries.explain import generate_explanation
from app.schemas.games import (
    ActualResultOut,
    GameDetail,
    GameSummary,
    OddsOut,
    PitcherOut,
    PitcherRecentStart,
    PredictionOut,
    TeamOut,
    TeamStatsOut,
    WeatherOut,
)

RECENT_STARTS_LIMIT = 5


def _team_out(team: Team) -> TeamOut:
    return TeamOut(id=team.id, name=team.name, abbreviation=team.abbreviation)


def _prediction_out(prediction: Prediction | None) -> PredictionOut | None:
    if prediction is None:
        return None
    return PredictionOut(
        predicted_label=prediction.predicted_label,
        nrfi_probability=prediction.nrfi_probability,
        yrfi_probability=prediction.yrfi_probability,
        confidence=prediction.confidence,
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        predicted_at=prediction.predicted_at,
    )


def _weather_out(game: Game) -> WeatherOut | None:
    """M8.5: only present once app.prediction.enrich has actually captured
    a reading for this game — a missing venue match or a not-yet-run
    enrichment step both mean "no weather", not an error.
    """
    if game.weather_temp_f is None or game.weather_captured_at is None:
        return None
    return WeatherOut(
        temp_f=game.weather_temp_f,
        conditions=game.weather_conditions,
        wind_mph=game.weather_wind_mph,
        wind_direction_deg=game.weather_wind_direction_deg,
        captured_at=game.weather_captured_at,
    )


def _odds_out(game: Game) -> OddsOut | None:
    if game.home_moneyline is None or game.away_moneyline is None:
        return None
    return OddsOut(
        home_moneyline=game.home_moneyline,
        away_moneyline=game.away_moneyline,
        bookmaker=game.odds_bookmaker,
        captured_at=game.odds_captured_at,
    )


def _actual_result_out(game: Game) -> ActualResultOut | None:
    if not game.is_labeled:
        return None
    return ActualResultOut(
        home_runs_1st=game.home_runs_1st,
        away_runs_1st=game.away_runs_1st,
        first_inning_runs=game.first_inning_runs,
        nrfi=game.nrfi,
        home_score=game.home_score,
        away_score=game.away_score,
    )


def _pitcher_out(
    pitcher: Pitcher | None, side: str, features: dict | None
) -> PitcherOut | None:
    """``side`` is "home" or "away" — selects that side's columns out of a
    prediction's stored feature snapshot, if there is one.
    """
    if pitcher is None:
        return None
    f = features or {}
    return PitcherOut(
        id=pitcher.id,
        full_name=pitcher.full_name,
        throws=pitcher.throws,
        k_rate_1st=f.get(f"{side}_sp_k_rate_1st"),
        bb_rate_1st=f.get(f"{side}_sp_bb_rate_1st"),
        nrfi_rate_career=f.get(f"{side}_sp_nrfi_rate"),
        nrfi_rate_season=f.get(f"{side}_sp_nrfi_rate_season"),
        nrfi_rate_last5=f.get(f"{side}_sp_nrfi_rate_recent"),
        starts_prior=f.get(f"{side}_sp_starts_prior"),
    )


def _team_stats_out(side: str, features: dict | None) -> TeamStatsOut | None:
    if not features:
        return None
    return TeamStatsOut(
        scored_1st_rate=features.get(f"{side}_team_scored_1st_rate"),
        scored_1st_rate_season=features.get(f"{side}_team_scored_1st_rate_season"),
        scored_1st_rate_recent=features.get(f"{side}_team_scored_1st_rate_recent"),
        scored_1st_rate_split=features.get(f"{side}_team_scored_1st_rate_split"),
        runs_1st_avg=features.get(f"{side}_team_runs_1st_avg"),
        k_rate_1st=features.get(f"{side}_team_k_rate_1st"),
        games_prior=features.get(f"{side}_team_games_prior"),
    )


def _champion_predictions(session: Session, game_pks: list[int]) -> dict[int, Prediction]:
    """The current champion's prediction per game, where one exists.

    A blank result (rather than a raised error) if M6 hasn't produced a
    champion yet — a dashboard with no predictions is still a dashboard.
    """
    if not game_pks:
        return {}
    try:
        _, version = champion_identity()
    except ChampionNotFoundError:
        return {}
    rows = session.scalars(
        select(Prediction).where(
            Prediction.game_pk.in_(game_pks), Prediction.model_version == version
        )
    )
    return {p.game_pk: p for p in rows}


def _champion_prediction(session: Session, game_pk: int) -> Prediction | None:
    predictions = _champion_predictions(session, [game_pk])
    return predictions.get(game_pk)


def _teams_by_id(session: Session, team_ids: set[int]) -> dict[int, Team]:
    if not team_ids:
        return {}
    return {t.id: t for t in session.scalars(select(Team).where(Team.id.in_(team_ids)))}


def _pitchers_by_id(session: Session, pitcher_ids: set[int]) -> dict[int, Pitcher]:
    if not pitcher_ids:
        return {}
    return {
        p.id: p for p in session.scalars(select(Pitcher).where(Pitcher.id.in_(pitcher_ids)))
    }


def games_for_date(
    session: Session,
    date: dt.date,
    prediction: str | None = None,
    min_confidence: float | None = None,
    team: str | None = None,
    sort_by: str | None = None,
) -> list[GameSummary]:
    """A date's slate — the dashboard's core listing.

    ``prediction`` filters to "NRFI"/"YRFI", ``min_confidence`` to
    confidence >= that value, ``team`` to a case-insensitive substring match
    on either side's name/abbreviation (requirements.md: search teams).
    ``sort_by="confidence"`` sorts descending — the only sort
    requirements.md asks for; games without a prediction sort last.
    """
    games = session.scalars(
        select(Game)
        .where(Game.game_date == date, Game.game_type == "R")
        .order_by(Game.start_time_utc)
    ).all()
    if not games:
        return []

    predictions = _champion_predictions(session, [g.game_pk for g in games])
    teams = _teams_by_id(
        session, {g.home_team_id for g in games} | {g.away_team_id for g in games}
    )
    pitcher_ids = {
        pid
        for g in games
        for pid in (g.home_probable_pitcher_id, g.away_probable_pitcher_id)
        if pid is not None
    }
    pitchers = _pitchers_by_id(session, pitcher_ids)

    rows = []
    for game in games:
        pred = predictions.get(game.game_pk)
        features = pred.features if pred else None
        rows.append(
            GameSummary(
                game_pk=game.game_pk,
                game_date=game.game_date,
                start_time_utc=game.start_time_utc,
                status=game.status,
                venue_name=game.venue_name,
                home_team=_team_out(teams[game.home_team_id]),
                away_team=_team_out(teams[game.away_team_id]),
                home_pitcher=_pitcher_out(
                    pitchers.get(game.home_probable_pitcher_id), "home", features
                ),
                away_pitcher=_pitcher_out(
                    pitchers.get(game.away_probable_pitcher_id), "away", features
                ),
                prediction=_prediction_out(pred),
                weather=_weather_out(game),
            )
        )

    if team:
        needle = team.strip().upper()
        rows = [
            r
            for r in rows
            if needle in r.home_team.abbreviation.upper()
            or needle in r.away_team.abbreviation.upper()
            or needle in r.home_team.name.upper()
            or needle in r.away_team.name.upper()
        ]
    if prediction:
        wanted = prediction.strip().upper()
        rows = [r for r in rows if r.prediction and r.prediction.predicted_label == wanted]
    if min_confidence is not None:
        rows = [r for r in rows if r.prediction and r.prediction.confidence >= min_confidence]
    if sort_by == "confidence":
        rows.sort(
            key=lambda r: r.prediction.confidence if r.prediction else -1, reverse=True
        )

    return rows


def _recent_starts(
    session: Session, pitcher_id: int, before_date: dt.date, limit: int = RECENT_STARTS_LIMIT
) -> list[PitcherRecentStart]:
    """A starter's most recent outings strictly before ``before_date`` — the
    same as-of cutoff app.features.compute uses, so this never shows a start
    that hadn't happened yet as of the game being described.
    """
    rows = session.execute(
        select(
            PitcherGameStats.game_pk,
            Game.game_date,
            PitcherGameStats.runs_1st,
            Game.nrfi,
            PitcherGameStats.is_home,
            Game.home_team_id,
            Game.away_team_id,
        )
        .join(Game, Game.game_pk == PitcherGameStats.game_pk)
        .where(
            PitcherGameStats.pitcher_id == pitcher_id,
            PitcherGameStats.is_starter.is_(True),
            Game.game_date < before_date,
        )
        .order_by(Game.game_date.desc())
        .limit(limit)
    ).all()
    if not rows:
        return []

    team_ids = {r.home_team_id for r in rows} | {r.away_team_id for r in rows}
    teams = _teams_by_id(session, team_ids)

    starts = []
    for r in rows:
        opponent_id = r.away_team_id if r.is_home else r.home_team_id
        opponent = teams[opponent_id].abbreviation if opponent_id in teams else "?"
        starts.append(
            PitcherRecentStart(
                game_pk=r.game_pk,
                game_date=r.game_date,
                opponent=opponent,
                runs_1st=r.runs_1st,
                nrfi=r.nrfi,
            )
        )
    return starts


def game_detail(session: Session, game_pk: int) -> GameDetail | None:
    game = session.get(Game, game_pk)
    if game is None:
        return None

    prediction = _champion_prediction(session, game_pk)
    features = prediction.features if prediction else None

    home_team = session.get(Team, game.home_team_id)
    away_team = session.get(Team, game.away_team_id)
    home_pitcher_row = (
        session.get(Pitcher, game.home_probable_pitcher_id)
        if game.home_probable_pitcher_id
        else None
    )
    away_pitcher_row = (
        session.get(Pitcher, game.away_probable_pitcher_id)
        if game.away_probable_pitcher_id
        else None
    )

    home_pitcher = _pitcher_out(home_pitcher_row, "home", features)
    away_pitcher = _pitcher_out(away_pitcher_row, "away", features)
    if home_pitcher is not None:
        home_pitcher.recent_starts = _recent_starts(
            session, home_pitcher_row.id, game.game_date
        )
    if away_pitcher is not None:
        away_pitcher.recent_starts = _recent_starts(
            session, away_pitcher_row.id, game.game_date
        )

    return GameDetail(
        game_pk=game.game_pk,
        game_date=game.game_date,
        start_time_utc=game.start_time_utc,
        status=game.status,
        venue_name=game.venue_name,
        home_team=_team_out(home_team),
        away_team=_team_out(away_team),
        home_pitcher=home_pitcher,
        away_pitcher=away_pitcher,
        home_team_stats=_team_stats_out("home", features),
        away_team_stats=_team_stats_out("away", features),
        prediction=_prediction_out(prediction),
        explanation=generate_explanation(prediction) if prediction else [],
        actual_result=_actual_result_out(game),
        weather=_weather_out(game),
        odds=_odds_out(game),
    )
