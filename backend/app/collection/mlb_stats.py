"""MLB Stats API data collection (M1).

Pulls the daily MLB schedule and probable starting pitchers for a given date
from the MLB Stats API (statsapi.mlb.com), via the MLB-StatsAPI Python
wrapper. This is the operational/daily data source per research.md; the
Statcast historical backfill (M2) is a separate module.

Run directly to inspect a date's slate:

    python -m app.collection.mlb_stats                 # today
    python -m app.collection.mlb_stats --date 2025-07-01
    python -m app.collection.mlb_stats --date 2025-07-01 --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from dataclasses import asdict, dataclass

import statsapi


class MLBStatsAPIError(RuntimeError):
    """Raised when the MLB Stats API can't be reached or returns bad data."""


@dataclass(frozen=True)
class Game:
    """One scheduled MLB game, normalized from the raw schedule payload.

    Probable pitchers are ``None`` until MLB announces them. Scores are
    ``None`` for games that haven't started, and populated for in-progress
    or finished games (which is how past dates return boxscore-ish data).
    """

    game_id: int
    status: str
    away_team: str
    home_team: str
    away_team_id: int
    home_team_id: int
    venue: str | None
    start_time_utc: str | None
    away_probable_pitcher: str | None
    home_probable_pitcher: str | None
    away_score: int | None
    home_score: int | None
    doubleheader: bool
    game_num: int

    @property
    def matchup(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    @property
    def pitchers_announced(self) -> bool:
        """True only when BOTH starters are confirmed."""
        return bool(self.away_probable_pitcher and self.home_probable_pitcher)


def _clean_str(value: object) -> str | None:
    """Normalize the API's empty strings / whitespace to None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: object) -> int | None:
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _to_api_date(date: str | dt.date | None) -> str:
    """Accept ISO ``YYYY-MM-DD`` (or a date) and return the API's MM/DD/YYYY."""
    if date is None:
        date = dt.date.today()
    if isinstance(date, dt.date):
        return date.strftime("%m/%d/%Y")
    try:
        parsed = dt.date.fromisoformat(str(date))
    except ValueError as exc:
        raise MLBStatsAPIError(
            f"Invalid date {date!r}; expected ISO format YYYY-MM-DD"
        ) from exc
    return parsed.strftime("%m/%d/%Y")


def _to_game(raw: dict) -> Game:
    """Map one raw statsapi.schedule() dict into a Game."""
    doubleheader = _clean_str(raw.get("doubleheader")) or "N"
    return Game(
        game_id=_clean_int(raw.get("game_id")) or 0,
        status=_clean_str(raw.get("status")) or "Unknown",
        away_team=_clean_str(raw.get("away_name")) or "Unknown",
        home_team=_clean_str(raw.get("home_name")) or "Unknown",
        away_team_id=_clean_int(raw.get("away_id")) or 0,
        home_team_id=_clean_int(raw.get("home_id")) or 0,
        venue=_clean_str(raw.get("venue_name")),
        start_time_utc=_clean_str(raw.get("game_datetime")),
        away_probable_pitcher=_clean_str(raw.get("away_probable_pitcher")),
        home_probable_pitcher=_clean_str(raw.get("home_probable_pitcher")),
        away_score=_clean_int(raw.get("away_score")),
        home_score=_clean_int(raw.get("home_score")),
        # "Y" = traditional doubleheader, "S" = split; both mean 2 games.
        doubleheader=doubleheader in {"Y", "S"},
        game_num=_clean_int(raw.get("game_num")) or 1,
    )


def fetch_schedule(date: str | dt.date | None = None) -> list[Game]:
    """Return the MLB schedule for a date (default: today).

    ``date`` accepts an ISO string (YYYY-MM-DD) or a ``datetime.date``.
    Returns an empty list when no games are scheduled. Raises
    ``MLBStatsAPIError`` on a bad date or an API/network failure.
    """
    api_date = _to_api_date(date)
    try:
        raw_games = statsapi.schedule(date=api_date)
    except Exception as exc:  # requests errors, bad responses, etc.
        raise MLBStatsAPIError(
            f"Failed to fetch schedule for {api_date}: {exc}"
        ) from exc
    return [_to_game(g) for g in raw_games]


def _format_table(games: list[Game]) -> str:
    rows = []
    for g in games:
        away_p = g.away_probable_pitcher or "TBD"
        home_p = g.home_probable_pitcher or "TBD"
        score = ""
        if g.away_score is not None and g.home_score is not None:
            score = f"  [{g.away_score}-{g.home_score}]"
        dh = "  (DH)" if g.doubleheader else ""
        rows.append(
            f"  {g.matchup:<40} {g.status:<14} "
            f"{away_p} vs {home_p}{score}{dh}"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the MLB schedule and probable pitchers for a date."
    )
    parser.add_argument(
        "--date",
        help="Date in ISO format (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of a formatted table.",
    )
    args = parser.parse_args(argv)

    try:
        games = fetch_schedule(args.date)
    except MLBStatsAPIError as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.json:
        print(json.dumps([asdict(g) for g in games], indent=2))
        return 0

    label = args.date or dt.date.today().isoformat()
    if not games:
        print(f"No MLB games scheduled for {label}.")
        return 0

    announced = sum(1 for g in games if g.pitchers_announced)
    print(
        f"MLB schedule for {label} — {len(games)} game(s), "
        f"{announced} with both starters announced:\n"
    )
    print(_format_table(games))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
