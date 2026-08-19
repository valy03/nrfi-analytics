"""Tests for the M8.5 odds client (app.collection.odds).

``requests.get`` is stubbed — same pattern as test_weather.py.
"""

import requests as requests_module

import pytest

from app.collection import odds


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _event(home, away, bookmakers):
    return {
        "home_team": home,
        "away_team": away,
        "commence_time": "2026-08-19T20:10:00Z",
        "bookmakers": bookmakers,
    }


def _bookmaker(key, title, home, away, home_price, away_price):
    return {
        "key": key,
        "title": title,
        "markets": [
            {
                "key": "h2h",
                "outcomes": [
                    {"name": home, "price": home_price},
                    {"name": away, "price": away_price},
                ],
            }
        ],
    }


class _Settings:
    odds_api_key = "test-key"


# --- fetch_odds --------------------------------------------------------


def test_fetch_odds_requires_an_api_key(monkeypatch):
    class _NoKey:
        odds_api_key = ""

    monkeypatch.setattr(odds, "get_settings", lambda: _NoKey())

    with pytest.raises(odds.OddsAPIError):
        odds.fetch_odds()


def test_fetch_odds_wraps_request_failures(monkeypatch):
    monkeypatch.setattr(odds, "get_settings", lambda: _Settings())

    def boom(*a, **kw):
        raise requests_module.ConnectionError("no network")

    monkeypatch.setattr(odds.requests, "get", boom)

    with pytest.raises(odds.OddsAPIError):
        odds.fetch_odds()


# --- todays_moneylines ---------------------------------------------------


def test_todays_moneylines_picks_the_preferred_bookmaker(monkeypatch):
    event = _event(
        "Boston Red Sox",
        "New York Yankees",
        [
            _bookmaker("mybookieag", "MyBookie.ag", "Boston Red Sox", "New York Yankees", -150, 130),
            _bookmaker("draftkings", "DraftKings", "Boston Red Sox", "New York Yankees", -160, 140),
        ],
    )
    monkeypatch.setattr(odds, "get_settings", lambda: _Settings())
    monkeypatch.setattr(odds.requests, "get", lambda *a, **kw: _FakeResponse([event]))

    lines = odds.todays_moneylines()

    line = lines[("Boston Red Sox", "New York Yankees")]
    assert line.bookmaker == "DraftKings"
    assert line.home_moneyline == -160
    assert line.away_moneyline == 140


def test_todays_moneylines_falls_back_to_any_bookmaker(monkeypatch):
    event = _event(
        "Boston Red Sox",
        "New York Yankees",
        [_bookmaker("obscurebook", "Obscure Book", "Boston Red Sox", "New York Yankees", -110, -110)],
    )
    monkeypatch.setattr(odds, "get_settings", lambda: _Settings())
    monkeypatch.setattr(odds.requests, "get", lambda *a, **kw: _FakeResponse([event]))

    lines = odds.todays_moneylines()

    assert lines[("Boston Red Sox", "New York Yankees")].bookmaker == "Obscure Book"


def test_todays_moneylines_skips_a_game_with_no_bookmakers(monkeypatch):
    event = _event("Boston Red Sox", "New York Yankees", [])
    monkeypatch.setattr(odds, "get_settings", lambda: _Settings())
    monkeypatch.setattr(odds.requests, "get", lambda *a, **kw: _FakeResponse([event]))

    assert odds.todays_moneylines() == {}


def test_todays_moneylines_skips_a_game_missing_the_h2h_market(monkeypatch):
    event = _event(
        "Boston Red Sox",
        "New York Yankees",
        [{"key": "draftkings", "title": "DraftKings", "markets": [{"key": "totals", "outcomes": []}]}],
    )
    monkeypatch.setattr(odds, "get_settings", lambda: _Settings())
    monkeypatch.setattr(odds.requests, "get", lambda *a, **kw: _FakeResponse([event]))

    assert odds.todays_moneylines() == {}


def test_todays_moneylines_covers_the_whole_slate_in_one_call(monkeypatch):
    events = [
        _event(
            "Boston Red Sox", "New York Yankees",
            [_bookmaker("draftkings", "DraftKings", "Boston Red Sox", "New York Yankees", -150, 130)],
        ),
        _event(
            "Los Angeles Dodgers", "San Francisco Giants",
            [_bookmaker("draftkings", "DraftKings", "Los Angeles Dodgers", "San Francisco Giants", -200, 170)],
        ),
    ]
    calls = []
    monkeypatch.setattr(odds, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        odds.requests, "get", lambda *a, **kw: (calls.append(1), _FakeResponse(events))[1]
    )

    lines = odds.todays_moneylines()

    assert len(calls) == 1
    assert len(lines) == 2
