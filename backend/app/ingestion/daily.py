"""Daily load: M1 MLB Stats API schedule -> Postgres (M3).

This is the loader the M7 scheduled job will call. For a given date it:

1. upserts any probable starters into ``pitchers`` (FK target for games),
2. upserts the slate into ``games`` — matchup, venue, start time, status,
3. for games that are already final, pulls the linescore and writes the
   first-inning outcome + NRFI label.

Step 3 means today's games become labeled training rows the same night,
without waiting for the Statcast backfill to catch up. Where both sources
cover a game they agree: the label is first-inning runs either way.

Re-running for the same date updates in place — no duplicate rows.

Run it:
    python -m app.ingestion.daily                  # today
    python -m app.ingestion.daily --date 2025-07-01
    python -m app.ingestion.daily --start 2025-07-01 --end 2025-07-07
"""

from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy.orm import Session

from app.collection.mlb_stats import (
    Game as ScheduleGame,
    MLBStatsAPIError,
    fetch_first_inning_result,
    fetch_schedule,
    mlb_today,
)
from app.db.session import session_scope
from app.ingestion.teams import seed_teams
from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Game, Pitcher

# Statuses that mean the game is over and its linescore is trustworthy.
FINAL_STATUSES = {"Final", "Game Over", "Completed Early"}


class DailyIngestionError(RuntimeError):
    """Raised when a day's slate can't be loaded into Postgres."""


def _parse_start_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_pitcher_rows(games: list[ScheduleGame]) -> list[dict]:
    """Every announced starter on the slate, as ``pitchers`` payloads."""
    rows: dict[int, dict] = {}
    for game in games:
        pairs = (
            (game.away_probable_pitcher_id, game.away_probable_pitcher),
            (game.home_probable_pitcher_id, game.home_probable_pitcher),
        )
        for pitcher_id, name in pairs:
            if pitcher_id and name:
                rows[pitcher_id] = {"id": pitcher_id, "full_name": name}
    return list(rows.values())


def to_game_rows(games: list[ScheduleGame]) -> list[dict]:
    """Map schedule entries to ``games`` payloads."""
    rows = []
    for game in games:
        game_date = (
            dt.date.fromisoformat(game.game_date) if game.game_date else None
        )
        start_time = _parse_start_time(game.start_time_utc)
        if game_date is None and start_time is not None:
            game_date = start_time.date()
        if game_date is None:
            raise DailyIngestionError(
                f"Game {game.game_id} has no usable date in the schedule feed"
            )

        rows.append(
            {
                "game_pk": game.game_id,
                "game_date": game_date,
                "season": game_date.year,
                "game_type": game.game_type or "R",
                "status": game.status,
                "away_team_id": game.away_team_id,
                "home_team_id": game.home_team_id,
                "venue_id": game.venue_id,
                "venue_name": game.venue,
                "start_time_utc": start_time,
                "doubleheader": game.doubleheader,
                "game_num": game.game_num,
                "away_probable_pitcher_id": game.away_probable_pitcher_id,
                "home_probable_pitcher_id": game.home_probable_pitcher_id,
                "away_score": game.away_score,
                "home_score": game.home_score,
            }
        )
    return rows


def label_finished_games(
    session: Session, games: list[ScheduleGame], relabel: bool = False
) -> int:
    """Write first-inning results for finished games. Returns rows labeled.

    Already-labeled games are skipped unless ``relabel`` is set, so a daily
    job that runs several times a day makes at most one linescore call per
    game per day.
    """
    finished = [g for g in games if g.status in FINAL_STATUSES]
    if not finished:
        return 0

    stored = {
        g.game_pk: g
        for g in session.query(Game)
        .filter(Game.game_pk.in_([g.game_id for g in finished]))
        .all()
    }

    labeled = 0
    for game in finished:
        row = stored.get(game.game_id)
        if row is None or (row.nrfi is not None and not relabel):
            continue
        result = fetch_first_inning_result(game.game_id)
        if result is None:
            continue  # suspended/abandoned before the 1st finished
        row.away_runs_1st = result.away_runs
        row.home_runs_1st = result.home_runs
        row.first_inning_runs = result.total_runs
        row.nrfi = result.nrfi
        labeled += 1

    session.flush()
    return labeled


def load_date(
    session: Session,
    date: str | dt.date | None = None,
    label_results: bool = True,
    relabel: bool = False,
) -> tuple[UpsertCounts, UpsertCounts, int]:
    """Load one date's slate. Returns (pitchers, games, games_labeled)."""
    games = fetch_schedule(date, with_pitcher_ids=True)
    if not games:
        return UpsertCounts(), UpsertCounts(), 0

    pitcher_counts = upsert_rows(
        session, Pitcher, to_pitcher_rows(games), key_cols=["id"]
    )
    game_counts = upsert_rows(
        session, Game, to_game_rows(games), key_cols=["game_pk"]
    )
    labeled = (
        label_finished_games(session, games, relabel) if label_results else 0
    )
    return pitcher_counts, game_counts, labeled


def _date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    if start > end:
        raise DailyIngestionError(f"start {start} is after end {end}")
    return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load a date's MLB slate into Postgres."
    )
    parser.add_argument("--date", help="Single date (YYYY-MM-DD). Default: today.")
    parser.add_argument("--start", help="Start of a date range (YYYY-MM-DD).")
    parser.add_argument("--end", help="End of a date range (YYYY-MM-DD).")
    parser.add_argument(
        "--skip-teams",
        action="store_true",
        help="Don't refresh the team reference table first.",
    )
    parser.add_argument(
        "--no-results",
        action="store_true",
        help="Skip the linescore lookup for finished games.",
    )
    parser.add_argument(
        "--relabel",
        action="store_true",
        help="Re-pull first-inning results even for already-labeled games.",
    )
    args = parser.parse_args(argv)

    try:
        if args.start or args.end:
            if not (args.start and args.end):
                raise DailyIngestionError("--start and --end must be used together")
            dates = _date_range(
                dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
            )
        else:
            dates = [
                dt.date.fromisoformat(args.date) if args.date else mlb_today()
            ]

        with session_scope() as session:
            if not args.skip_teams:
                print(f"Teams: {seed_teams(session)}")
            totals = [UpsertCounts(), UpsertCounts(), 0]
            for date in dates:
                pitchers, games, labeled = load_date(
                    session,
                    date,
                    label_results=not args.no_results,
                    relabel=args.relabel,
                )
                totals[0] += pitchers
                totals[1] += games
                totals[2] += labeled
                if len(dates) > 1:
                    print(f"  {date}: games {games}, {labeled} labeled")
    except (DailyIngestionError, MLBStatsAPIError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    span = dates[0].isoformat()
    if len(dates) > 1:
        span = f"{dates[0]}..{dates[-1]}"
    print(
        f"Daily load complete for {span}.\n"
        f"  Pitchers: {totals[0]}\n"
        f"  Games:    {totals[1]}\n"
        f"  Labeled:  {totals[2]} finished game(s) got a first-inning result"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
