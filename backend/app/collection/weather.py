"""Weather collection (M8.5): OpenWeather free tier.

Display-only per research.md — not a model input, so nothing here touches
the feature pipeline. ``fetch_forecast`` and ``reading_from_entries`` are
split apart deliberately: a doubleheader's two games share a venue, and
app.prediction.enrich fetches the forecast once per unique venue per job
run and picks each game its own closest bucket from that one response,
rather than hitting the API twice for the same park.

The free tier doesn't offer a point-in-time forecast for an arbitrary future
hour — the closest available primitive is the 5-day/3-hour-step forecast
(``/data/2.5/forecast``), so a game's conditions are the forecast bucket
nearest its actual first-pitch time, not a live "right now" reading. The
two can differ by up to ~90 minutes if the job runs well before first pitch,
which is an acceptable approximation for a display-only field.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests

from app.config import get_settings

FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
REQUEST_TIMEOUT = 10


class WeatherAPIError(RuntimeError):
    """Raised when OpenWeather can't be reached or returns bad data."""


@dataclass(frozen=True)
class WeatherReading:
    temp_f: float
    conditions: str
    wind_mph: float
    wind_direction_deg: int | None
    captured_at: dt.datetime


def fetch_forecast(lat: float, lon: float) -> list[dict]:
    """Raw 3-hour-step forecast entries for the next 5 days at a venue."""
    settings = get_settings()
    if not settings.openweather_api_key:
        raise WeatherAPIError("OPENWEATHER_API_KEY is not configured")
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "lat": lat,
                "lon": lon,
                "appid": settings.openweather_api_key,
                "units": "imperial",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherAPIError(f"OpenWeather request failed: {exc}") from exc
    return response.json().get("list", [])


def reading_from_entries(
    entries: list[dict], target: dt.datetime
) -> WeatherReading | None:
    """The forecast bucket closest to ``target`` (UTC), parsed into a
    reading. ``None`` if there are no usable entries — an empty forecast,
    or one missing the fields this needs.
    """
    if not entries:
        return None
    closest = min(
        entries,
        key=lambda e: abs(
            dt.datetime.fromtimestamp(e["dt"], tz=dt.timezone.utc) - target
        ),
    )
    main = closest.get("main") or {}
    if main.get("temp") is None:
        return None
    weather = (closest.get("weather") or [{}])[0]
    wind = closest.get("wind") or {}
    return WeatherReading(
        temp_f=main["temp"],
        conditions=weather.get("main", "Unknown"),
        wind_mph=wind.get("speed", 0.0),
        wind_direction_deg=wind.get("deg"),
        captured_at=dt.datetime.now(dt.timezone.utc),
    )


def reading_for(lat: float, lon: float, at: dt.datetime) -> WeatherReading | None:
    """Convenience wrapper: fetch and pick in one call, for a single game."""
    return reading_from_entries(fetch_forecast(lat, lon), at)
