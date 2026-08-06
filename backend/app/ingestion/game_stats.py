"""Load derived first-inning box scores into Postgres (M4).

Takes the two parquets written by ``app.collection.statcast_boxscore`` and
fills the ``pitcher_game_stats`` / ``team_game_stats`` tables that M3 defined
but left empty. These are the raw per-game observations the feature pipeline
aggregates over.

Pitchers are seeded from the same file — Statcast carries the person id, name
and handedness, so no extra API calls are needed to satisfy the foreign key.

Run it:
    python -m app.ingestion.game_stats
    python -m app.ingestion.game_stats --season 2024
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collection.statcast_boxscore import PITCHER_PARQUET, TEAM_PARQUET
from app.db.session import session_scope
from app.ingestion.teams import team_id_by_abbreviation
from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Game, Pitcher, PitcherGameStats, TeamGameStats

DEFAULT_PROCESSED_DIR = Path("data/processed")
BATCH_SIZE = 5000


class GameStatsIngestionError(RuntimeError):
    """Raised when derived box scores can't be loaded."""


def _load(path: Path, season: int | None) -> pd.DataFrame:
    if not path.exists():
        raise GameStatsIngestionError(
            f"No dataset at {path}. Derive it first: "
            "python -m app.collection.statcast_boxscore"
        )
    df = pd.read_parquet(path)
    if season is not None:
        df = df[pd.to_datetime(df["game_date"]).dt.year == season]
    return df


def _known_game_pks(session: Session, game_pks: set[int]) -> set[int]:
    """Which of these games are actually in ``games``.

    Box scores can only attach to a game that's been loaded (M3). Rather than
    let a foreign key blow up the whole batch, unknown games are reported and
    skipped — they mean the M2/M3 load is behind, not that the data is bad.
    """
    known: set[int] = set()
    ordered = sorted(game_pks)
    for start in range(0, len(ordered), BATCH_SIZE):
        chunk = ordered[start : start + BATCH_SIZE]
        known.update(
            session.scalars(
                select(Game.game_pk).where(Game.game_pk.in_(chunk))
            )
        )
    return known


def load_pitcher_stats(
    session: Session,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    season: int | None = None,
    progress: bool = True,
) -> tuple[UpsertCounts, UpsertCounts, int]:
    """Load pitcher lines. Returns (pitchers, stats, skipped_rows)."""
    df = _load(processed_dir / PITCHER_PARQUET, season)
    if df.empty:
        return UpsertCounts(), UpsertCounts(), 0

    team_ids = team_id_by_abbreviation(session)
    known = _known_game_pks(session, set(df["game_pk"].astype(int)))

    pitcher_rows: dict[int, dict] = {}
    stat_rows: list[dict] = []
    skipped = 0

    for record in df.to_dict("records"):
        game_pk = int(record["game_pk"])
        team_id = team_ids.get(record["team_abbr"])
        if game_pk not in known or team_id is None:
            skipped += 1
            continue

        pitcher_id = int(record["pitcher_id"])
        pitcher_rows[pitcher_id] = {
            "id": pitcher_id,
            "full_name": record["pitcher_name"],
            "throws": record["throws"],
        }
        stat_rows.append(
            {
                "game_pk": game_pk,
                "pitcher_id": pitcher_id,
                "team_id": team_id,
                "is_home": bool(record["is_home"]),
                "is_starter": bool(record["is_starter"]),
                "batters_faced_1st": int(record["batters_faced_1st"]),
                "hits_1st": int(record["hits_1st"]),
                "runs_1st": int(record["runs_1st"]),
                "walks_1st": int(record["walks_1st"]),
                "strikeouts_1st": int(record["strikeouts_1st"]),
                "home_runs_1st": int(record["home_runs_1st"]),
                "pitches_1st": int(record["pitches_1st"]),
            }
        )

    # Pitchers first — the stats rows foreign-key to them.
    pitcher_counts = upsert_rows(
        session, Pitcher, list(pitcher_rows.values()), key_cols=["id"]
    )
    stat_counts = _batched_upsert(
        session, PitcherGameStats, stat_rows, ["game_pk", "pitcher_id"], progress
    )
    return pitcher_counts, stat_counts, skipped


def load_team_stats(
    session: Session,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    season: int | None = None,
    progress: bool = True,
) -> tuple[UpsertCounts, int]:
    """Load team lines. Returns (stats, skipped_rows)."""
    df = _load(processed_dir / TEAM_PARQUET, season)
    if df.empty:
        return UpsertCounts(), 0

    team_ids = team_id_by_abbreviation(session)
    known = _known_game_pks(session, set(df["game_pk"].astype(int)))

    rows: list[dict] = []
    skipped = 0
    for record in df.to_dict("records"):
        game_pk = int(record["game_pk"])
        team_id = team_ids.get(record["team_abbr"])
        if game_pk not in known or team_id is None:
            skipped += 1
            continue
        rows.append(
            {
                "game_pk": game_pk,
                "team_id": team_id,
                "is_home": bool(record["is_home"]),
                "runs_1st": int(record["runs_1st"]),
                "hits_1st": int(record["hits_1st"]),
                "walks_1st": int(record["walks_1st"]),
                "strikeouts_1st": int(record["strikeouts_1st"]),
                "batters_1st": int(record["batters_1st"]),
            }
        )

    counts = _batched_upsert(
        session, TeamGameStats, rows, ["game_pk", "team_id"], progress
    )
    return counts, skipped


def _batched_upsert(
    session: Session,
    model,
    rows: list[dict],
    key_cols: list[str],
    progress: bool,
) -> UpsertCounts:
    counts = UpsertCounts()
    for start in range(0, len(rows), BATCH_SIZE):
        counts += upsert_rows(
            session, model, rows[start : start + BATCH_SIZE], key_cols=key_cols
        )
        if progress:
            print(f"  {min(start + BATCH_SIZE, len(rows))}/{len(rows)} rows")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load derived first-inning box scores into Postgres."
    )
    parser.add_argument(
        "--processed-dir",
        default=str(DEFAULT_PROCESSED_DIR),
        help="Directory holding the derived parquets.",
    )
    parser.add_argument("--season", type=int, help="Load a single season only.")
    args = parser.parse_args(argv)

    processed_dir = Path(args.processed_dir)
    try:
        with session_scope() as session:
            print("Pitcher lines:")
            pitchers, pitcher_stats, p_skipped = load_pitcher_stats(
                session, processed_dir, args.season
            )
            print("Team lines:")
            team_stats, t_skipped = load_team_stats(
                session, processed_dir, args.season
            )
    except GameStatsIngestionError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(
        f"\nBox score load complete.\n"
        f"  Pitchers:           {pitchers}\n"
        f"  pitcher_game_stats: {pitcher_stats}\n"
        f"  team_game_stats:    {team_stats}"
    )
    if p_skipped or t_skipped:
        print(
            f"  Skipped {p_skipped} pitcher / {t_skipped} team rows for games "
            "not in the database — run the M3 historical load to catch up."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
