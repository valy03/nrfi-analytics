"""Historical load: M2 Statcast parquet -> Postgres ``games`` (M3).

The backfill (M2) produces one NRFI-labeled row per game in
``data/processed/nrfi_games.parquet``. This walks that file into the
``games`` table, resolving Statcast's team abbreviations to team ids.

Only the columns Statcast actually knows are written — matchup, date, and
the first-inning outcome. Schedule details (venue, start time, probable
pitchers) stay null here and get filled in by the daily loader, which is
safe because the upsert never overwrites a stored value with ``None``.

Run it:
    python -m app.ingestion.historical
    python -m app.ingestion.historical --season 2024
    python -m app.ingestion.historical --parquet data/processed/nrfi_games.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.session import session_scope
from app.ingestion.teams import seed_teams, team_id_by_abbreviation
from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Game

DEFAULT_PARQUET = Path("data/processed/nrfi_games.parquet")

# Written in batches so a full 18k-game load doesn't build one giant
# statement (and so progress is visible on a long run).
BATCH_SIZE = 2000


class HistoricalIngestionError(RuntimeError):
    """Raised when the Statcast dataset can't be loaded into Postgres."""


def load_dataset(path: Path = DEFAULT_PARQUET) -> pd.DataFrame:
    if not path.exists():
        raise HistoricalIngestionError(
            f"No dataset at {path}. Run the M2 backfill first: "
            "python -m app.collection.statcast_backfill"
        )
    return pd.read_parquet(path)


def to_game_rows(
    df: pd.DataFrame, team_ids: dict[str, int]
) -> list[dict]:
    """Map labeled Statcast game rows to ``games`` payloads.

    Raises if an abbreviation can't be resolved — a silently dropped game
    would quietly shrink the training set, which is exactly the kind of bug
    that's invisible until model metrics look "fine but off".
    """
    unknown = sorted(
        (set(df["away_team"]) | set(df["home_team"])) - set(team_ids)
    )
    if unknown:
        raise HistoricalIngestionError(
            f"Unmapped team abbreviations: {unknown}. Seed teams first "
            "(python -m app.ingestion.teams) or add an alias in "
            "app/ingestion/teams.py."
        )

    rows = []
    for record in df.to_dict("records"):
        rows.append(
            {
                "game_pk": int(record["game_pk"]),
                "game_date": pd.Timestamp(record["game_date"]).date(),
                "season": int(record["season"]),
                "game_type": str(record["game_type"]),
                "away_team_id": team_ids[record["away_team"]],
                "home_team_id": team_ids[record["home_team"]],
                "away_runs_1st": int(record["away_runs_1st"]),
                "home_runs_1st": int(record["home_runs_1st"]),
                "first_inning_runs": int(record["first_inning_runs"]),
                "nrfi": bool(record["nrfi"]),
            }
        )
    return rows


def load_historical(
    session: Session,
    path: Path = DEFAULT_PARQUET,
    season: int | None = None,
    batch_size: int = BATCH_SIZE,
    progress: bool = True,
) -> UpsertCounts:
    """Load (or refresh) the historical dataset in ``games``."""
    df = load_dataset(path)
    if season is not None:
        df = df[df["season"] == season]
    if df.empty:
        return UpsertCounts()

    team_ids = team_id_by_abbreviation(session)
    rows = to_game_rows(df, team_ids)

    counts = UpsertCounts()
    for start in range(0, len(rows), batch_size):
        counts += upsert_rows(
            session, Game, rows[start : start + batch_size], key_cols=["game_pk"]
        )
        if progress:
            print(f"  {min(start + batch_size, len(rows))}/{len(rows)} games")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load the M2 Statcast NRFI dataset into Postgres."
    )
    parser.add_argument(
        "--parquet",
        default=str(DEFAULT_PARQUET),
        help="Path to the M2 per-game dataset.",
    )
    parser.add_argument(
        "--season", type=int, help="Load a single season instead of all."
    )
    parser.add_argument(
        "--skip-teams",
        action="store_true",
        help="Don't refresh the team reference table first (offline runs).",
    )
    args = parser.parse_args(argv)

    try:
        with session_scope() as session:
            if not args.skip_teams:
                print(f"Teams: {seed_teams(session)}")
            counts = load_historical(
                session, Path(args.parquet), season=args.season
            )
    except HistoricalIngestionError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Historical load complete — games: {counts} ({counts.total} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
