"""HTTP-level tests for the M8 history endpoints — wiring only; business
logic is covered in tests/test_queries_history.py.
"""

import datetime as dt

from app.models import Game, Prediction, PredictionResult, Team


def _graded_prediction(session):
    session.add_all(
        [
            Team(id=111, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=147, name="New York Yankees", abbreviation="NYY"),
        ]
    )
    session.flush()
    game = Game(
        game_pk=1,
        game_date=dt.date(2026, 8, 1),
        season=2026,
        home_team_id=111,
        away_team_id=147,
        status="Final",
        nrfi=True,
    )
    session.add(game)
    session.flush()
    prediction = Prediction(
        game_pk=1,
        model_name="logreg",
        model_version="m5-v1",
        predicted_label="NRFI",
        nrfi_probability=0.6,
        yrfi_probability=0.4,
        confidence=0.2,
    )
    session.add(prediction)
    session.flush()
    session.add(
        PredictionResult(
            prediction_id=prediction.id, game_pk=1, actual_label="NRFI", correct=True
        )
    )
    session.flush()


def test_prediction_history_endpoint(client, session):
    _graded_prediction(session)

    response = client.get("/api/history/predictions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["correct"] is True


def test_accuracy_endpoint(client, session):
    _graded_prediction(session)

    response = client.get("/api/history/accuracy")

    assert response.status_code == 200
    body = response.json()
    assert body["overall"]["total"] == 1
    assert body["overall"]["accuracy"] == 1.0


def test_accuracy_endpoint_with_no_data_yet(client, session):
    response = client.get("/api/history/accuracy")

    assert response.status_code == 200
    body = response.json()
    assert body["overall"] == {
        "period": "overall",
        "total": 0,
        "correct": 0,
        "accuracy": None,
        "win_rate": None,
        "roi": None,
    }
