"""Statcast historical backfill (M2).

Pulls pitch-level Statcast data from Baseball Savant (via pybaseball) for a
date range, and collapses it into one row per game with a derived NRFI/YRFI
label. This is the historical training-data source per research.md; the daily
operational side is MLB Stats API (see mlb_stats.py).

How the NRFI label is derived
------------------------------
Statcast rows are pitch-level and carry the running game score *after* each
play in ``post_away_score`` / ``post_home_score``, plus ``inning`` and
``inning_topbot``. Because the first inning is the first scoring opportunity
of the game, a team's cumulative score at the end of inning 1 IS its
first-inning run total. So for each game we take the max post-score across
all ``inning == 1`` rows: that's the runs each side scored in the 1st. NRFI
== both are zero.

Caching / idempotency
---------------------
Raw pulls are chunked by calendar month and cached to parquet under
``data/raw/statcast/``; a chunk already on disk is never re-downloaded
(unless ``--force``). The derived per-game dataset is merged into
``data/processed/nrfi_games.parquet``, deduped by ``game_pk`` — so re-running
any range never duplicates games.

Run it:
    python -m app.collection.statcast_backfill --start 2023-04-01 --end 2023-04-07
    python -m app.collection.statcast_backfill --start 2018-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import time
from pathlib import Path

import pandas as pd
import pybaseball

from app.collection.mlb_stats import mlb_today

# Baseball Savant occasionally drops a connection mid-download (IncompleteRead)
# on a long backfill. Re-fetching a chunk is harmless, so we retry transient
# failures a few times before giving up on the whole run.
DEFAULT_RETRIES = 4
DEFAULT_RETRY_WAIT = 5.0  # seconds between attempts

# MLB regular season spans roughly late March through October (postseason
# into early November). We skip pure-offseason months so we don't waste pulls
# on dates that return nothing.
SEASON_MONTHS = range(3, 12)  # March (3) through November (11)

DEFAULT_DATA_DIR = Path("data")

# Column order for the per-game output.
GAME_COLUMNS = [
    "game_pk",
    "game_date",
    "season",
    "game_type",
    "away_team",
    "home_team",
    "away_runs_1st",
    "home_runs_1st",
    "first_inning_runs",
    "nrfi",
]


class StatcastBackfillError(RuntimeError):
    """Raised when the backfill can't fetch or process Statcast data."""


def _month_chunks(
    start: dt.date, end: dt.date, season_months: range = SEASON_MONTHS
) -> list[tuple[str, str]]:
    """Split [start, end] into per-calendar-month (start, end) ISO strings.

    Months entirely outside ``season_months`` are skipped. Each returned range
    is clipped to the overall [start, end] window.
    """
    if start > end:
        raise StatcastBackfillError(f"start {start} is after end {end}")

    chunks: list[tuple[str, str]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        if month in season_months:
            first = dt.date(year, month, 1)
            last = dt.date(year, month, calendar.monthrange(year, month)[1])
            chunk_start = max(first, start)
            chunk_end = min(last, end)
            if chunk_start <= chunk_end:
                chunks.append((chunk_start.isoformat(), chunk_end.isoformat()))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return chunks


def fetch_statcast_chunk(
    start_date: str,
    end_date: str,
    raw_dir: Path,
    force: bool = False,
    retries: int = DEFAULT_RETRIES,
    retry_wait: float = DEFAULT_RETRY_WAIT,
) -> pd.DataFrame:
    """Return Statcast pitch data for a range, caching it to parquet.

    A cached parquet for the exact range is reused unless ``force`` is set.
    Transient network failures (e.g. Savant dropping the connection) are
    retried up to ``retries`` times before the run is aborted.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"statcast_{start_date}_{end_date}.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            df = pybaseball.statcast(start_dt=start_date, end_dt=end_date)
            if df is None:
                df = pd.DataFrame()
            df.to_parquet(path, index=False)
            return df
        except Exception as exc:  # network / Savant failures
            last_exc = exc
            if attempt < retries:
                print(
                    f"  [retry] {start_date}..{end_date} attempt {attempt}/"
                    f"{retries} failed ({exc}); retrying in {retry_wait:.0f}s"
                )
                time.sleep(retry_wait)

    raise StatcastBackfillError(
        f"Failed to pull Statcast {start_date}..{end_date} after {retries} "
        f"attempts: {last_exc}"
    ) from last_exc


def collect_game_labels(
    start: dt.date,
    end: dt.date,
    raw_dir: Path,
    regular_season_only: bool = True,
    force: bool = False,
    retries: int = DEFAULT_RETRIES,
    retry_wait: float = DEFAULT_RETRY_WAIT,
) -> pd.DataFrame:
    """Fetch + label every monthly chunk in [start, end], one at a time.

    Crucially, pitch-level data is derived to per-game rows chunk-by-chunk and
    only the small labeled frames are kept — the full multi-season pitch
    dataset (gigabytes) is never held in memory at once. Returns the
    concatenated per-game labels (deduped later by the caller).
    """
    chunks = _month_chunks(start, end)
    per_game_frames: list[pd.DataFrame] = []
    for i, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        df = fetch_statcast_chunk(
            chunk_start, chunk_end, raw_dir, force, retries, retry_wait
        )
        labeled = derive_game_labels(df, regular_season_only)
        del df  # release the month's pitch data before the next chunk
        if not labeled.empty:
            per_game_frames.append(labeled)
        print(f"  [{i}/{len(chunks)}] {chunk_start}..{chunk_end}: "
              f"{len(labeled)} games")

    if not per_game_frames:
        return pd.DataFrame(columns=GAME_COLUMNS)
    return pd.concat(per_game_frames, ignore_index=True)


def derive_game_labels(
    df: pd.DataFrame, regular_season_only: bool = True
) -> pd.DataFrame:
    """Collapse pitch-level Statcast rows into one labeled row per game."""
    if df.empty:
        return pd.DataFrame(columns=GAME_COLUMNS)

    data = df
    if regular_season_only and "game_type" in data.columns:
        data = data[data["game_type"] == "R"]

    first = data[data["inning"] == 1].copy()
    if first.empty:
        return pd.DataFrame(columns=GAME_COLUMNS)

    first["post_away_score"] = pd.to_numeric(
        first["post_away_score"], errors="coerce"
    )
    first["post_home_score"] = pd.to_numeric(
        first["post_home_score"], errors="coerce"
    )

    games = (
        first.groupby("game_pk")
        .agg(
            game_date=("game_date", "first"),
            game_type=("game_type", "first"),
            away_team=("away_team", "first"),
            home_team=("home_team", "first"),
            away_runs_1st=("post_away_score", "max"),
            home_runs_1st=("post_home_score", "max"),
        )
        .reset_index()
    )

    games["away_runs_1st"] = games["away_runs_1st"].fillna(0).astype(int)
    games["home_runs_1st"] = games["home_runs_1st"].fillna(0).astype(int)
    games["first_inning_runs"] = games["away_runs_1st"] + games["home_runs_1st"]
    games["nrfi"] = (games["first_inning_runs"] == 0).astype(int)
    games["season"] = pd.to_datetime(games["game_date"]).dt.year
    games["game_pk"] = games["game_pk"].astype(int)

    return games[GAME_COLUMNS].sort_values(["game_date", "game_pk"]).reset_index(
        drop=True
    )


def run_backfill(
    start: dt.date,
    end: dt.date,
    data_dir: Path = DEFAULT_DATA_DIR,
    force: bool = False,
    regular_season_only: bool = True,
    retries: int = DEFAULT_RETRIES,
    retry_wait: float = DEFAULT_RETRY_WAIT,
) -> pd.DataFrame:
    """Full backfill: fetch+label each chunk → merge into the processed dataset.

    Processes chunk-by-chunk so the full multi-season pitch dataset is never
    held in memory at once. Returns the complete (merged, deduped) per-game
    dataset.
    """
    raw_dir = data_dir / "raw" / "statcast"
    processed_path = data_dir / "processed" / "nrfi_games.parquet"

    new_games = collect_game_labels(
        start, end, raw_dir, regular_season_only, force, retries, retry_wait
    )

    processed_path.parent.mkdir(parents=True, exist_ok=True)
    if processed_path.exists():
        existing = pd.read_parquet(processed_path)
        combined = pd.concat([existing, new_games], ignore_index=True)
    else:
        combined = new_games

    combined = (
        combined.drop_duplicates(subset="game_pk", keep="last")
        .sort_values(["game_date", "game_pk"])
        .reset_index(drop=True)
    )
    combined.to_parquet(processed_path, index=False)
    return combined


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise StatcastBackfillError(
            f"Invalid date {value!r}; expected ISO format YYYY-MM-DD"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill historical Statcast data and derive NRFI labels."
    )
    parser.add_argument(
        "--start", default="2018-01-01", help="Start date (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--end",
        default=mlb_today().isoformat(),
        help="End date (YYYY-MM-DD). Defaults to today (US Eastern).",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Where to store raw/ and processed/ data.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download chunks even if cached.",
    )
    parser.add_argument(
        "--include-postseason",
        action="store_true",
        help="Include non-regular-season games (spring/postseason).",
    )
    args = parser.parse_args(argv)

    try:
        start = _parse_date(args.start)
        end = _parse_date(args.end)
        games = run_backfill(
            start,
            end,
            data_dir=Path(args.data_dir),
            force=args.force,
            regular_season_only=not args.include_postseason,
        )
    except StatcastBackfillError as exc:
        print(f"ERROR: {exc}")
        return 1

    total = len(games)
    if total == 0:
        print(f"No games found for {args.start}..{args.end}.")
        return 0

    nrfi = int(games["nrfi"].sum())
    rate = nrfi / total
    processed_path = Path(args.data_dir) / "processed" / "nrfi_games.parquet"
    print(
        f"Backfill complete for {args.start}..{args.end}.\n"
        f"  Processed dataset: {processed_path} "
        f"({total} total games across all backfilled ranges)\n"
        f"  NRFI: {nrfi} ({rate:.1%})  |  YRFI: {total - nrfi} "
        f"({1 - rate:.1%})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())