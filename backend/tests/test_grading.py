"""Tests for M8's prediction grading (app.grading.results).

Real ORM rows against the in-memory SQLite ``session`` fixture, same
pattern as test_models.py / test_prediction.py — grading is a plain join
over data other milestones already populate, no external stub needed.
"""

import datetime as dt

from app.grading.results import grade_predictions
from app.models import Game, Prediction, PredictionResult, Team


def _team_and_game(session, game_pk=745804, nrfi=None, game_date=dt.date(2025, 7, 1)):
    away = Team(id=147, name="New York Yankees", abbreviation="NYY")
    home = Team(id=111, name="Boston Red Sox", abbreviation="BOS")
    session.add_all([away, home])
    session.flush()
    game = Game(
        game_pk=game_pk,
        game_date=game_date,
        season=game_date.year,
        away_team_id=away.id,
        home_team_id=home.id,
        nrfi=nrfi,
    )
    session.add(game)
    session.flush()
    return game


def _prediction(game_pk, predicted_label="NRFI", model_version="m5-v1"):
    return Prediction(
        game_pk=game_pk,
        model_name="logreg",
        model_version=model_version,
        predicted_label=predicted_label,
        nrfi_probability=0.6 if predicted_label == "NRFI" else 0.4,
        yrfi_probability=0.4 if predicted_label == "NRFI" else 0.6,
        confidence=0.2,
    )


def test_a_correct_prediction_is_graded_correct(session):
    game = _team_and_game(session, nrfi=True)
    prediction = _prediction(game.game_pk, predicted_label="NRFI")
    session.add(prediction)
    session.flush()

    graded = grade_predictions(session)

    assert graded == 1
    result = session.query(PredictionResult).one()
    assert result.actual_label == "NRFI"
    assert result.correct is True
    assert result.prediction_id == prediction.id


def test_a_wrong_prediction_is_graded_incorrect(session):
    game = _team_and_game(session, nrfi=False)
    prediction = _prediction(game.game_pk, predicted_label="NRFI")
    session.add(prediction)
    session.flush()

    grade_predictions(session)

    result = session.query(PredictionResult).one()
    assert result.actual_label == "YRFI"
    assert result.correct is False


def test_a_prediction_for_an_unfinished_game_is_not_graded(session):
    game = _team_and_game(session, nrfi=None)
    session.add(_prediction(game.game_pk))
    session.flush()

    graded = grade_predictions(session)

    assert graded == 0
    assert session.query(PredictionResult).count() == 0


def test_grading_is_idempotent(session):
    game = _team_and_game(session, nrfi=True)
    session.add(_prediction(game.game_pk))
    session.flush()
    grade_predictions(session)

    graded_again = grade_predictions(session)

    assert graded_again == 0
    assert session.query(PredictionResult).count() == 1


def test_grading_can_be_scoped_to_a_date(session):
    early = _team_and_game(session, game_pk=1, nrfi=True, game_date=dt.date(2025, 7, 1))
    late = Game(
        game_pk=2,
        game_date=dt.date(2025, 7, 2),
        season=2025,
        away_team_id=early.away_team_id,
        home_team_id=early.home_team_id,
        nrfi=True,
    )
    session.add(late)
    session.flush()
    session.add_all([_prediction(early.game_pk), _prediction(late.game_pk)])
    session.flush()

    graded = grade_predictions(session, date=dt.date(2025, 7, 2))

    assert graded == 1
    assert session.query(PredictionResult).one().game_pk == late.game_pk


def test_grading_handles_multiple_model_versions_for_the_same_game(session):
    """Two model versions can each have a prediction for the same game
    (Prediction's uq is per (game_pk, model_version)) — both get graded.
    """
    game = _team_and_game(session, nrfi=True)
    session.add_all(
        [
            _prediction(game.game_pk, predicted_label="NRFI", model_version="m5-v1"),
            _prediction(game.game_pk, predicted_label="YRFI", model_version="m6-xgb-v1"),
        ]
    )
    session.flush()

    graded = grade_predictions(session)

    assert graded == 2
    results = {r.prediction.model_version: r.correct for r in session.query(PredictionResult)}
    assert results == {"m5-v1": True, "m6-xgb-v1": False}
