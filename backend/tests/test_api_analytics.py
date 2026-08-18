"""HTTP-level tests for the M8 analytics endpoints — wiring only; business
logic is covered in tests/test_queries_analytics.py.
"""

import datetime as dt

from app.models import Game, Team


def _labeled_games(session):
    session.add_all(
        [
            Team(id=111, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=147, name="New York Yankees", abbreviation="NYY"),
        ]
    )
    session.flush()
    session.add(
        Game(
            game_pk=1,
            game_date=dt.date(2026, 4, 1),
            season=2026,
            home_team_id=111,
            away_team_id=147,
            status="Final",
            nrfi=True,
        )
    )
    session.flush()


def test_nrfi_frequency_endpoint(client, session):
    _labeled_games(session)

    response = client.get("/api/analytics/nrfi-frequency")

    assert response.status_code == 200
    assert response.json() == [{"period": "2026", "games": 1, "nrfi_rate": 1.0}]


def test_pitcher_leaderboard_endpoint_empty(client, session):
    response = client.get("/api/analytics/pitchers")

    assert response.status_code == 200
    assert response.json() == []


def test_team_leaderboard_endpoint_empty(client, session):
    response = client.get("/api/analytics/teams")

    assert response.status_code == 200
    assert response.json() == []


def test_model_performance_endpoint_empty(client, session):
    response = client.get("/api/analytics/models")

    assert response.status_code == 200
    assert response.json() == []
