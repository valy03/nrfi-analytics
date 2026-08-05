"""Schema-level tests for the M3 models.

These assert the constraints the rest of the pipeline will rely on: that a
game can't reference a team that doesn't exist, that a prediction is unique
per model version, and that an unplayed game is legitimately unlabeled.
"""

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Game,
    Pitcher,
    PitcherGameStats,
    Prediction,
    PredictionResult,
    Team,
    TeamGameStats,
)


def _teams(session):
    away = Team(id=147, name="New York Yankees", abbreviation="NYY")
    home = Team(id=111, name="Boston Red Sox", abbreviation="BOS")
    session.add_all([away, home])
    session.flush()
    return away, home


def _game(session, game_pk=745804, **kwargs):
    away, home = _teams(session)
    game = Game(
        game_pk=game_pk,
        game_date=dt.date(2025, 7, 1),
        season=2025,
        away_team_id=away.id,
        home_team_id=home.id,
        **kwargs,
    )
    session.add(game)
    session.flush()
    return game


def test_game_defaults_and_relationships(session):
    game = _game(session)

    assert game.game_type == "R"
    assert game.doubleheader is False
    assert game.game_num == 1
    assert game.away_team.abbreviation == "NYY"
    assert game.home_team.abbreviation == "BOS"
    # An unplayed game has no outcome yet — that's the row M7 predicts on.
    assert game.nrfi is None
    assert game.is_labeled is False


def test_labeled_game_reports_is_labeled(session):
    game = _game(
        session, away_runs_1st=0, home_runs_1st=0, first_inning_runs=0, nrfi=True
    )
    assert game.is_labeled is True


def test_game_requires_existing_teams(session):
    session.add(
        Game(
            game_pk=1,
            game_date=dt.date(2025, 7, 1),
            season=2025,
            away_team_id=999,  # no such team
            home_team_id=998,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_game_cannot_play_itself(session):
    away, _ = _teams(session)
    session.add(
        Game(
            game_pk=2,
            game_date=dt.date(2025, 7, 1),
            season=2025,
            away_team_id=away.id,
            home_team_id=away.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_one_prediction_per_game_and_model_version(session):
    game = _game(session)
    for _ in range(2):
        session.add(
            Prediction(
                game_pk=game.game_pk,
                model_name="logreg",
                model_version="v1",
                predicted_label="NRFI",
                nrfi_probability=0.61,
                yrfi_probability=0.39,
                confidence=0.22,
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_different_model_versions_coexist(session):
    game = _game(session)
    for version in ("v1", "v2"):
        session.add(
            Prediction(
                game_pk=game.game_pk,
                model_name="xgboost",
                model_version=version,
                predicted_label="NRFI",
                nrfi_probability=0.6,
                yrfi_probability=0.4,
                confidence=0.2,
            )
        )
    session.flush()
    assert len(game.predictions) == 2


def test_prediction_label_must_be_valid(session):
    game = _game(session)
    session.add(
        Prediction(
            game_pk=game.game_pk,
            model_name="logreg",
            model_version="v1",
            predicted_label="MAYB",
            nrfi_probability=0.5,
            yrfi_probability=0.5,
            confidence=0.0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_prediction_result_grades_a_prediction(session):
    game = _game(
        session, away_runs_1st=1, home_runs_1st=0, first_inning_runs=1, nrfi=False
    )
    prediction = Prediction(
        game_pk=game.game_pk,
        model_name="logreg",
        model_version="v1",
        predicted_label="NRFI",
        nrfi_probability=0.7,
        yrfi_probability=0.3,
        confidence=0.4,
        features={"pitcher_nrfi_pct": 0.63},
    )
    session.add(prediction)
    session.flush()

    session.add(
        PredictionResult(
            prediction_id=prediction.id,
            game_pk=game.game_pk,
            actual_label="YRFI",
            correct=False,
        )
    )
    session.flush()

    assert prediction.result.correct is False
    assert prediction.features == {"pitcher_nrfi_pct": 0.63}


def test_per_game_stats_are_unique_per_participant(session):
    game = _game(session)
    pitcher = Pitcher(id=543037, full_name="Gerrit Cole")
    session.add(pitcher)
    session.flush()

    for _ in range(2):
        session.add(
            PitcherGameStats(
                game_pk=game.game_pk,
                pitcher_id=pitcher.id,
                team_id=game.away_team_id,
                is_home=False,
                runs_1st=0,
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_game_cascades_to_its_children(session):
    game = _game(session)
    session.add(
        TeamGameStats(
            game_pk=game.game_pk, team_id=game.home_team_id, is_home=True, runs_1st=2
        )
    )
    session.add(
        Prediction(
            game_pk=game.game_pk,
            model_name="logreg",
            model_version="v1",
            predicted_label="YRFI",
            nrfi_probability=0.4,
            yrfi_probability=0.6,
            confidence=0.2,
        )
    )
    session.flush()

    session.delete(game)
    session.flush()

    assert session.query(TeamGameStats).count() == 0
    assert session.query(Prediction).count() == 0
