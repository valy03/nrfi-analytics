"""Tests for the M8.5 weather client (app.collection.weather).

``requests.get`` is stubbed — same offline-first spirit as the rest of the
collection layer (test_mlb_stats.py stubs the statsapi wrapper).
"""

import datetime as dt

import pytest

from app.collection import weather


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


def _entry(hours_from_epoch, temp=72.0, conditions="Clear", wind=5.0, deg=180):
    return {
        "dt": hours_from_epoch * 3600,
        "main": {"temp": temp},
        "weather": [{"main": conditions}],
        "wind": {"speed": wind, "deg": deg},
    }


# --- fetch_forecast --------------------------------------------------------


def test_fetch_forecast_requires_an_api_key(monkeypatch):
    class _Settings:
        openweather_api_key = ""

    monkeypatch.setattr(weather, "get_settings", lambda: _Settings())

    with pytest.raises(weather.WeatherAPIError):
        weather.fetch_forecast(42.0, -71.0)


def test_fetch_forecast_wraps_request_failures(monkeypatch):
    class _Settings:
        openweather_api_key = "test-key"

    monkeypatch.setattr(weather, "get_settings", lambda: _Settings())

    import requests as requests_module

    def boom(*a, **kw):
        raise requests_module.ConnectionError("no network")

    monkeypatch.setattr(weather.requests, "get", boom)

    with pytest.raises(weather.WeatherAPIError):
        weather.fetch_forecast(42.0, -71.0)


def test_fetch_forecast_returns_the_list_field(monkeypatch):
    class _Settings:
        openweather_api_key = "test-key"

    monkeypatch.setattr(weather, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        weather.requests, "get", lambda *a, **kw: _FakeResponse({"list": [_entry(0)]})
    )

    entries = weather.fetch_forecast(42.0, -71.0)

    assert len(entries) == 1


# --- reading_from_entries ---------------------------------------------------


def test_reading_from_entries_picks_the_closest_bucket():
    target = dt.datetime.fromtimestamp(5 * 3600, tz=dt.timezone.utc)
    entries = [_entry(0, temp=60.0), _entry(3, temp=70.0), _entry(6, temp=80.0)]

    reading = weather.reading_from_entries(entries, target)

    assert reading.temp_f == 80.0  # bucket at hour 6 is closest to hour 5


def test_reading_from_entries_parses_conditions_and_wind():
    target = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)
    entries = [_entry(0, temp=68.5, conditions="Rain", wind=12.3, deg=270)]

    reading = weather.reading_from_entries(entries, target)

    assert reading.conditions == "Rain"
    assert reading.wind_mph == pytest.approx(12.3)
    assert reading.wind_direction_deg == 270


def test_reading_from_entries_is_none_for_an_empty_forecast():
    assert weather.reading_from_entries([], dt.datetime.now(dt.timezone.utc)) is None


def test_reading_from_entries_is_none_when_temp_is_missing():
    entry = {"dt": 0, "main": {}, "weather": [{"main": "Clear"}], "wind": {}}
    assert weather.reading_from_entries([entry], dt.datetime.now(dt.timezone.utc)) is None


def test_reading_from_entries_defaults_missing_wind_to_zero():
    entry = {"dt": 0, "main": {"temp": 70.0}, "weather": [{"main": "Clear"}], "wind": {}}
    reading = weather.reading_from_entries([entry], dt.datetime.fromtimestamp(0, tz=dt.timezone.utc))

    assert reading.wind_mph == 0.0
    assert reading.wind_direction_deg is None


# --- reading_for -------------------------------------------------------


def test_reading_for_combines_fetch_and_pick(monkeypatch):
    class _Settings:
        openweather_api_key = "test-key"

    monkeypatch.setattr(weather, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        weather.requests, "get", lambda *a, **kw: _FakeResponse({"list": [_entry(0, temp=55.0)]})
    )

    reading = weather.reading_for(42.0, -71.0, dt.datetime.fromtimestamp(0, tz=dt.timezone.utc))

    assert reading.temp_f == 55.0
