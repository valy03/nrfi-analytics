"""HTTP-level tests for the M8 games endpoints.

Exercises the FastAPI routes end to end (request in, JSON out) against the
in-memory SQLite session — app.queries.games already has thorough
query-level tests, so these focus on wiring: status codes, query-param
plumbing, and response shape, not every business rule again.
"""

import datetime as dt

import pytest

from app.models import Game, Pitcher, Prediction, Team
from app.queries import games as games_queries

HOME_TEAM, AWAY_TEAM = 111, 147
HOME_SP, AWAY_SP = 201, 202
GAME_DATE = dt.date(2026, 8, 18)


@pytest.fixture
def champion(monkeypatch):
    monkeypatch.setattr(games_queries, "champion_identity", lambda: ("logreg", "m5-v1"))


def _seed_game(session, game_pk=1):
    session.add_all(
        [
            Team(id=HOME_TEAM, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=AWAY_TEAM, name="New York Yankees", abbreviation="NYY"),
            Pitcher(id=HOME_SP, full_name="Home Starter"),
            Pitcher(id=AWAY_SP, full_name="Away Starter"),
        ]
    )
    session.flush()
    game = Game(
        game_pk=game_pk,
        game_date=GAME_DATE,
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Scheduled",
        home_probable_pitcher_id=HOME_SP,
        away_probable_pitcher_id=AWAY_SP,
    )
    session.add(game)
    session.flush()
    session.add(
        Prediction(
            game_pk=game_pk,
            model_name="logreg",
            model_version="m5-v1",
            predicted_label="NRFI",
            nrfi_probability=0.6,
            yrfi_probability=0.4,
            confidence=0.2,
            features={"home_sp_nrfi_rate": 0.7, "away_sp_nrfi_rate": 0.6},
        )
    )
    session.flush()
    return game


def test_list_games_returns_the_slate_for_a_date(client, session, champion):
    _seed_game(session)

    response = client.get("/api/games", params={"date": GAME_DATE.isoformat()})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["home_team"]["abbreviation"] == "BOS"
    assert body[0]["prediction"]["predicted_label"] == "NRFI"


def test_list_games_returns_empty_list_for_a_quiet_date(client, session):
    response = client.get("/api/games", params={"date": "2026-01-01"})

    assert response.status_code == 200
    assert response.json() == []


def test_list_games_filters_by_prediction_label(client, session, champion):
    _seed_game(session)

    matching = client.get(
        "/api/games", params={"date": GAME_DATE.isoformat(), "prediction": "NRFI"}
    )
    non_matching = client.get(
        "/api/games", params={"date": GAME_DATE.isoformat(), "prediction": "YRFI"}
    )

    assert len(matching.json()) == 1
    assert non_matching.json() == []


def test_list_games_rejects_an_invalid_prediction_filter(client, session):
    response = client.get(
        "/api/games", params={"date": GAME_DATE.isoformat(), "prediction": "MAYBE"}
    )

    assert response.status_code == 422


def test_get_game_returns_full_detail(client, session, champion):
    game = _seed_game(session)

    response = client.get(f"/api/games/{game.game_pk}")

    assert response.status_code == 200
    body = response.json()
    assert body["game_pk"] == game.game_pk
    assert body["prediction"]["nrfi_probability"] == pytest.approx(0.6)
    assert isinstance(body["explanation"], list)
    assert body["actual_result"] is None


def test_get_game_404s_for_an_unknown_game(client, session):
    response = client.get("/api/games/999999")

    assert response.status_code == 404
