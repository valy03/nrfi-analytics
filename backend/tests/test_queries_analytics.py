"""Tests for the M8 analytics queries (app.queries.analytics)."""

import datetime as dt

import pytest

from app.models import (
    Game,
    Pitcher,
    PitcherGameStats,
    Prediction,
    PredictionResult,
    Team,
    TeamGameStats,
)
from app.queries import analytics as analytics_queries

HOME_TEAM, AWAY_TEAM = 111, 147
PITCHER = 201


def _teams_and_pitcher(session):
    session.add_all(
        [
            Team(id=HOME_TEAM, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=AWAY_TEAM, name="New York Yankees", abbreviation="NYY"),
            Pitcher(id=PITCHER, full_name="Some Starter"),
        ]
    )
    session.flush()


def _game(session, game_pk, date, nrfi):
    game = Game(
        game_pk=game_pk,
        game_date=date,
        season=date.year,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Final",
        nrfi=nrfi,
    )
    session.add(game)
    session.flush()
    return game


# --- nrfi_frequency ---------------------------------------------------


def test_nrfi_frequency_groups_by_season(session):
    _teams_and_pitcher(session)
    _game(session, 1, dt.date(2024, 4, 1), nrfi=True)
    _game(session, 2, dt.date(2024, 4, 2), nrfi=False)
    _game(session, 3, dt.date(2025, 4, 1), nrfi=True)

    points = analytics_queries.nrfi_frequency(session)

    assert [p.period for p in points] == ["2024", "2025"]
    assert points[0].games == 2
    assert points[0].nrfi_rate == pytest.approx(0.5)
    assert points[1].nrfi_rate == pytest.approx(1.0)


def test_nrfi_frequency_ignores_unlabeled_games(session):
    _teams_and_pitcher(session)
    game = Game(
        game_pk=1,
        game_date=dt.date(2026, 8, 18),
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Scheduled",
    )
    session.add(game)
    session.flush()

    assert analytics_queries.nrfi_frequency(session) == []


# --- pitcher_leaderboard ---------------------------------------------------


def test_pitcher_leaderboard_computes_nrfi_rate(session):
    _teams_and_pitcher(session)
    for i, runs in enumerate([0, 0, 0, 1]):
        game = _game(session, i, dt.date(2026, 4, 1) + dt.timedelta(days=i), nrfi=(runs == 0))
        session.add(
            PitcherGameStats(
                game_pk=game.game_pk,
                pitcher_id=PITCHER,
                team_id=HOME_TEAM,
                is_home=True,
                is_starter=True,
                runs_1st=runs,
            )
        )
    session.flush()

    leaderboard = analytics_queries.pitcher_leaderboard(session, min_starts=4)

    assert len(leaderboard) == 1
    entry = leaderboard[0]
    assert entry.pitcher_id == PITCHER
    assert entry.starts == 4
    assert entry.nrfi_rate == pytest.approx(0.75)
    assert entry.runs_1st_avg == pytest.approx(0.25)


def test_pitcher_leaderboard_excludes_pitchers_below_the_start_floor(session):
    _teams_and_pitcher(session)
    game = _game(session, 1, dt.date(2026, 4, 1), nrfi=True)
    session.add(
        PitcherGameStats(
            game_pk=game.game_pk, pitcher_id=PITCHER, team_id=HOME_TEAM,
            is_home=True, is_starter=True, runs_1st=0,
        )
    )
    session.flush()

    assert analytics_queries.pitcher_leaderboard(session, min_starts=10) == []


def test_pitcher_leaderboard_excludes_relief_appearances(session):
    _teams_and_pitcher(session)
    game = _game(session, 1, dt.date(2026, 4, 1), nrfi=True)
    session.add(
        PitcherGameStats(
            game_pk=game.game_pk, pitcher_id=PITCHER, team_id=HOME_TEAM,
            is_home=True, is_starter=False, runs_1st=0,
        )
    )
    session.flush()

    assert analytics_queries.pitcher_leaderboard(session, min_starts=1) == []


# --- team_leaderboard ---------------------------------------------------


def test_team_leaderboard_ranks_quietest_offense_first(session):
    _teams_and_pitcher(session)
    for i in range(10):
        game = _game(session, i, dt.date(2026, 4, 1) + dt.timedelta(days=i), nrfi=True)
        session.add_all(
            [
                TeamGameStats(
                    game_pk=game.game_pk, team_id=HOME_TEAM, is_home=True,
                    runs_1st=1 if i < 8 else 0,  # scores 80% of the time
                ),
                TeamGameStats(
                    game_pk=game.game_pk, team_id=AWAY_TEAM, is_home=False,
                    runs_1st=1 if i < 2 else 0,  # scores 20% of the time
                ),
            ]
        )
    session.flush()

    leaderboard = analytics_queries.team_leaderboard(session, min_games=10)

    assert [entry.abbreviation for entry in leaderboard] == ["NYY", "BOS"]
    assert leaderboard[0].scored_1st_rate == pytest.approx(0.2)
    assert leaderboard[1].scored_1st_rate == pytest.approx(0.8)


# --- model_performance ---------------------------------------------------


def test_model_performance_computes_accuracy_per_model_version(session):
    _teams_and_pitcher(session)
    game = _game(session, 1, dt.date(2026, 4, 1), nrfi=True)
    good = Prediction(
        game_pk=game.game_pk, model_name="xgboost", model_version="m6-xgb-v1",
        predicted_label="NRFI", nrfi_probability=0.6, yrfi_probability=0.4, confidence=0.2,
    )
    bad = Prediction(
        game_pk=game.game_pk, model_name="logreg", model_version="m5-v1",
        predicted_label="YRFI", nrfi_probability=0.4, yrfi_probability=0.6, confidence=0.2,
    )
    session.add_all([good, bad])
    session.flush()
    session.add_all(
        [
            PredictionResult(
                prediction_id=good.id, game_pk=game.game_pk, actual_label="NRFI", correct=True
            ),
            PredictionResult(
                prediction_id=bad.id, game_pk=game.game_pk, actual_label="NRFI", correct=False
            ),
        ]
    )

    performance = analytics_queries.model_performance(session)

    by_version = {p.model_version: p for p in performance}
    assert by_version["m6-xgb-v1"].accuracy == pytest.approx(1.0)
    assert by_version["m5-v1"].accuracy == pytest.approx(0.0)


def test_model_performance_is_empty_when_nothing_is_graded(session):
    assert analytics_queries.model_performance(session) == []
