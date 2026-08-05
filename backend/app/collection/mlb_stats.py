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
from dataclasses import asdict, dataclass, replace

from zoneinfo import ZoneInfo

import statsapi

# MLB's "game day" is Eastern, not UTC. On a UTC host at 23:40 ET the two
# disagree, and a daily job would silently pull tomorrow's slate — so every
# "today" in this project resolves through mlb_today().
MLB_TIMEZONE = ZoneInfo("America/New_York")


class MLBStatsAPIError(RuntimeError):
    """Raised when the MLB Stats API can't be reached or returns bad data."""


def mlb_today() -> dt.date:
    """Today's date in MLB's scheduling timezone (US Eastern)."""
    return dt.datetime.now(MLB_TIMEZONE).date()


@dataclass(frozen=True)
class Game:
    """One scheduled MLB game, normalized from the raw schedule payload.

    Probable pitchers are ``None`` until MLB announces them. Scores are
    ``None`` for games that haven't started, and populated for in-progress
    or finished games (which is how past dates return boxscore-ish data).

    Pitcher *ids* are only populated when ``fetch_schedule`` is called with
    ``with_pitcher_ids=True`` — the wrapper's schedule feed carries names
    only, so ids cost a second (hydrated) request. See M3 ingestion, which
    needs them as foreign keys.
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
    game_date: str | None = None
    game_type: str | None = None
    venue_id: int | None = None
    away_probable_pitcher_id: int | None = None
    home_probable_pitcher_id: int | None = None

    @property
    def matchup(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    @property
    def pitchers_announced(self) -> bool:
        """True only when BOTH starters are confirmed."""
        return bool(self.away_probable_pitcher and self.home_probable_pitcher)

    @property
    def is_final(self) -> bool:
        return self.status == "Final"


@dataclass(frozen=True)
class FirstInningResult:
    """First-inning runs for one game, straight from the linescore.

    This is the operational counterpart to the M2 Statcast label: it lets a
    daily run label today's games as soon as the 1st is in the books, without
    waiting on a Savant backfill.
    """

    game_id: int
    away_runs: int
    home_runs: int

    @property
    def total_runs(self) -> int:
        return self.away_runs + self.home_runs

    @property
    def nrfi(self) -> bool:
        return self.total_runs == 0


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
        date = mlb_today()
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
        game_date=_clean_str(raw.get("game_date")),
        game_type=_clean_str(raw.get("game_type")),
        venue_id=_clean_int(raw.get("venue_id")),
    )


def fetch_probable_pitcher_ids(
    date: str | dt.date | None = None,
) -> dict[int, tuple[int | None, int | None]]:
    """Map ``game_id -> (away_pitcher_id, home_pitcher_id)`` for a date.

    The MLB-StatsAPI wrapper's ``schedule()`` exposes probable pitchers by
    name only. Ids come from the raw endpoint with ``probablePitcher``
    hydrated — which is what M3 needs to key the ``pitchers`` table on the
    MLB person id rather than on a name string.
    """
    api_date = _to_api_date(date)
    try:
        payload = statsapi.get(
            "schedule",
            {"sportId": 1, "date": api_date, "hydrate": "probablePitcher"},
        )
    except Exception as exc:
        raise MLBStatsAPIError(
            f"Failed to fetch probable pitcher ids for {api_date}: {exc}"
        ) from exc

    ids: dict[int, tuple[int | None, int | None]] = {}
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            game_id = _clean_int(game.get("gamePk"))
            if game_id is None:
                continue
            teams = game.get("teams", {})
            ids[game_id] = tuple(  # type: ignore[assignment]
                _clean_int(
                    (teams.get(side, {}).get("probablePitcher") or {}).get("id")
                )
                for side in ("away", "home")
            )
    return ids


def fetch_schedule(
    date: str | dt.date | None = None, with_pitcher_ids: bool = False
) -> list[Game]:
    """Return the MLB schedule for a date (default: today).

    ``date`` accepts an ISO string (YYYY-MM-DD) or a ``datetime.date``.
    Returns an empty list when no games are scheduled. Raises
    ``MLBStatsAPIError`` on a bad date or an API/network failure.

    ``with_pitcher_ids`` costs one extra request and fills in
    ``away/home_probable_pitcher_id``; it's off by default because only the
    database ingestion (M3) needs the ids.
    """
    api_date = _to_api_date(date)
    try:
        raw_games = statsapi.schedule(date=api_date)
    except Exception as exc:  # requests errors, bad responses, etc.
        raise MLBStatsAPIError(
            f"Failed to fetch schedule for {api_date}: {exc}"
        ) from exc

    games = [_to_game(g) for g in raw_games]
    if not (with_pitcher_ids and games):
        return games

    pitcher_ids = fetch_probable_pitcher_ids(date)
    return [
        replace(
            g,
            away_probable_pitcher_id=pitcher_ids.get(g.game_id, (None, None))[0],
            home_probable_pitcher_id=pitcher_ids.get(g.game_id, (None, None))[1],
        )
        for g in games
    ]


def fetch_first_inning_result(game_id: int) -> FirstInningResult | None:
    """Return first-inning runs for a game, or ``None`` if the 1st isn't done.

    Reads the linescore rather than the boxscore because the linescore is
    inning-indexed — exactly the shape the NRFI label needs.
    """
    try:
        linescore = statsapi.get("game_linescore", {"gamePk": game_id})
    except Exception as exc:
        raise MLBStatsAPIError(
            f"Failed to fetch linescore for game {game_id}: {exc}"
        ) from exc

    for inning in linescore.get("innings", []):
        if inning.get("num") != 1:
            continue
        away = _clean_int(inning.get("away", {}).get("runs"))
        home = _clean_int(inning.get("home", {}).get("runs"))
        if away is None or home is None:
            return None  # 1st still in progress (bottom half not batted yet)
        return FirstInningResult(game_id=game_id, away_runs=away, home_runs=home)
    return None


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

    label = args.date or mlb_today().isoformat()
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
