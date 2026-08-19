"""Tests for M8.5 weather/odds enrichment (app.prediction.enrich).

Real ORM rows against the in-memory SQLite ``session`` fixture; the
collection-layer clients (app.collection.weather / .odds) are stubbed at
the point enrich.py calls them, same pattern used throughout M7/M8's tests.
"""

import datetime as dt

import pytest

from app.collection.odds import MoneylineOdds
from app.collection.weather import WeatherReading
from app.models import Game, Team, Venue
from app.prediction import enrich

HOME_TEAM, AWAY_TEAM = 111, 147
VENUE = 3
GAME_DATE = dt.date(2026, 8, 18)
START_TIME = dt.datetime(2026, 8, 18, 23, 5, tzinfo=dt.timezone.utc)


def _teams_and_venue(session):
    session.add_all(
        [
            Team(id=HOME_TEAM, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=AWAY_TEAM, name="New York Yankees", abbreviation="NYY"),
            Venue(id=VENUE, name="Fenway Park", city="Boston", latitude=42.346456, longitude=-71.097441),
        ]
    )
    session.flush()


def _game(session, game_pk=1, venue_id=VENUE, start_time=START_TIME, **kwargs):
    game = Game(
        game_pk=game_pk,
        game_date=GAME_DATE,
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Scheduled",
        venue_id=venue_id,
        start_time_utc=start_time,
        **kwargs,
    )
    session.add(game)
    session.flush()
    return game


def _reading(temp=70.0):
    return WeatherReading(
        temp_f=temp, conditions="Clear", wind_mph=5.0, wind_direction_deg=180,
        captured_at=dt.datetime.now(dt.timezone.utc),
    )


# --- enrich_weather ---------------------------------------------------


def test_enrich_weather_writes_a_reading_onto_the_game(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session)
    monkeypatch.setattr(
        enrich.weather_collection, "fetch_forecast", lambda lat, lon: [{"stub": True}]
    )
    monkeypatch.setattr(
        enrich.weather_collection, "reading_from_entries", lambda entries, target: _reading(68.0)
    )

    counts = enrich.enrich_weather(session, [game.game_pk])

    assert counts.updated == 1
    session.refresh(game)
    assert game.weather_temp_f == pytest.approx(68.0)
    assert game.weather_conditions == "Clear"


def test_enrich_weather_fetches_once_per_shared_venue(session, monkeypatch):
    """A doubleheader's two games share a venue — one forecast fetch."""
    _teams_and_venue(session)
    g1 = _game(session, game_pk=1)
    g2 = _game(session, game_pk=2, start_time=START_TIME + dt.timedelta(hours=3))

    calls = []

    def fake_fetch(lat, lon):
        calls.append((lat, lon))
        return [{"stub": True}]

    monkeypatch.setattr(enrich.weather_collection, "fetch_forecast", fake_fetch)
    monkeypatch.setattr(
        enrich.weather_collection, "reading_from_entries", lambda entries, target: _reading()
    )

    enrich.enrich_weather(session, [g1.game_pk, g2.game_pk])

    assert len(calls) == 1


def test_enrich_weather_skips_a_game_with_an_unknown_venue(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session, venue_id=99999)  # not seeded

    counts = enrich.enrich_weather(session, [game.game_pk])

    assert counts.total == 0


def test_enrich_weather_skips_a_game_with_no_start_time(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session, start_time=None)

    counts = enrich.enrich_weather(session, [game.game_pk])

    assert counts.total == 0


def test_enrich_weather_survives_an_api_failure(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session)

    def boom(lat, lon):
        raise enrich.weather_collection.WeatherAPIError("nope")

    monkeypatch.setattr(enrich.weather_collection, "fetch_forecast", boom)

    counts = enrich.enrich_weather(session, [game.game_pk])

    assert counts.total == 0  # doesn't raise, doesn't write anything


def test_enrich_weather_is_a_no_op_for_an_empty_game_list(session):
    assert enrich.enrich_weather(session, []).total == 0


# --- enrich_odds ---------------------------------------------------------


def test_enrich_odds_writes_moneylines_onto_the_game(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session)
    line = MoneylineOdds(
        home_team="Boston Red Sox", away_team="New York Yankees",
        home_moneyline=-150, away_moneyline=130, bookmaker="DraftKings",
        captured_at=dt.datetime.now(dt.timezone.utc),
    )
    monkeypatch.setattr(
        enrich.odds_collection, "todays_moneylines",
        lambda: {("Boston Red Sox", "New York Yankees"): line},
    )

    counts = enrich.enrich_odds(session, [game.game_pk])

    assert counts.updated == 1
    session.refresh(game)
    assert game.home_moneyline == -150
    assert game.away_moneyline == 130
    assert game.odds_bookmaker == "DraftKings"


def test_enrich_odds_skips_a_game_with_no_matching_line(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session)
    monkeypatch.setattr(enrich.odds_collection, "todays_moneylines", lambda: {})

    counts = enrich.enrich_odds(session, [game.game_pk])

    assert counts.total == 0


def test_enrich_odds_survives_an_api_failure(session, monkeypatch):
    _teams_and_venue(session)
    game = _game(session)

    def boom():
        raise enrich.odds_collection.OddsAPIError("nope")

    monkeypatch.setattr(enrich.odds_collection, "todays_moneylines", boom)

    counts = enrich.enrich_odds(session, [game.game_pk])

    assert counts.total == 0


def test_enrich_odds_makes_one_call_for_the_whole_slate(session, monkeypatch):
    _teams_and_venue(session)
    g1 = _game(session, game_pk=1)
    other_away = Team(id=200, name="Toronto Blue Jays", abbreviation="TOR")
    session.add(other_away)
    session.flush()
    g2 = Game(
        game_pk=2, game_date=GAME_DATE, season=2026,
        home_team_id=HOME_TEAM, away_team_id=200, status="Scheduled",
        venue_id=VENUE, start_time_utc=START_TIME,
    )
    session.add(g2)
    session.flush()

    calls = []

    def fake_moneylines():
        calls.append(1)
        return {}

    monkeypatch.setattr(enrich.odds_collection, "todays_moneylines", fake_moneylines)

    enrich.enrich_odds(session, [g1.game_pk, g2.game_pk])

    assert len(calls) == 1


def test_enrich_odds_is_a_no_op_for_an_empty_game_list(session):
    assert enrich.enrich_odds(session, []).total == 0
