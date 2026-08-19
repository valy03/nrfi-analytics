"""Betting odds collection (M8.5): The Odds API free tier.

Display-only per research.md — not a model input. One request covers the
*entire* day's MLB slate (the endpoint returns every upcoming game with all
its bookmakers' odds in one payload), which is what keeps this well within
the free-tier budget regardless of slate size: the call that covers 2 games
covers 15 just as well.

(research.md's number for the free tier — 25 requests/day — is stale; a
live check during M8.5 showed a 500-request quota. Doesn't change anything
here: one call/day was already the design either way.)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests

from app.config import get_settings

ODDS_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
REQUEST_TIMEOUT = 10

# Preference order when a game has lines from multiple books. DraftKings is
# a commonly used reference line; anything else still beats showing no odds
# at all, so this is a preference, not a requirement.
PREFERRED_BOOKMAKERS = ["draftkings", "fanduel", "betmgm"]


class OddsAPIError(RuntimeError):
    """Raised when The Odds API can't be reached or returns bad data."""


@dataclass(frozen=True)
class MoneylineOdds:
    home_team: str
    away_team: str
    home_moneyline: int
    away_moneyline: int
    bookmaker: str
    captured_at: dt.datetime


def fetch_odds() -> list[dict]:
    """Raw payload — every upcoming MLB game with every bookmaker's line."""
    settings = get_settings()
    if not settings.odds_api_key:
        raise OddsAPIError("ODDS_API_KEY is not configured")
    try:
        response = requests.get(
            ODDS_URL,
            params={
                "apiKey": settings.odds_api_key,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OddsAPIError(f"The Odds API request failed: {exc}") from exc
    return response.json()


def _pick_bookmaker(bookmakers: list[dict]) -> dict | None:
    by_key = {b.get("key"): b for b in bookmakers}
    for preferred in PREFERRED_BOOKMAKERS:
        if preferred in by_key:
            return by_key[preferred]
    return bookmakers[0] if bookmakers else None


def _moneylines_from_event(event: dict) -> MoneylineOdds | None:
    bookmaker = _pick_bookmaker(event.get("bookmakers") or [])
    if bookmaker is None:
        return None
    markets = bookmaker.get("markets") or []
    h2h = next((m for m in markets if m.get("key") == "h2h"), None)
    if h2h is None:
        return None
    prices = {o["name"]: o["price"] for o in h2h.get("outcomes", [])}
    home_team, away_team = event.get("home_team"), event.get("away_team")
    if home_team not in prices or away_team not in prices:
        return None
    return MoneylineOdds(
        home_team=home_team,
        away_team=away_team,
        home_moneyline=prices[home_team],
        away_moneyline=prices[away_team],
        bookmaker=bookmaker.get("title") or bookmaker.get("key", "unknown"),
        captured_at=dt.datetime.now(dt.timezone.utc),
    )


def todays_moneylines() -> dict[tuple[str, str], MoneylineOdds]:
    """One API call for the whole slate, keyed by (home_team, away_team)
    exactly as The Odds API names them — app.prediction.enrich matches
    those names against our own ``teams.name`` column.
    """
    lines: dict[tuple[str, str], MoneylineOdds] = {}
    for event in fetch_odds():
        parsed = _moneylines_from_event(event)
        if parsed is not None:
            lines[(parsed.home_team, parsed.away_team)] = parsed
    return lines
