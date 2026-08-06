"""First-inning box scores from Statcast pitch data (M4).

M2 collapsed pitch data into one NRFI label per game. That's enough to train
on, but not enough to build features *from*: to know a pitcher's first-inning
track record you need to know who started each game and what happened to
them, which the label doesn't carry.

This module re-reads the same cached Statcast chunks and derives two
per-game tables:

- **pitcher lines** — one row per pitcher who appeared in the 1st, with
  batters faced, hits, walks, strikeouts and runs allowed
- **team lines** — one row per team's half of the 1st, with runs, hits,
  walks, strikeouts and batters sent to the plate

Identifying the starter
-----------------------
The pitcher who threw the first pitch of a half-inning started it. Top of
the 1st means the away team is batting, so that's the *home* team's starter;
bottom of the 1st is the away team's. Relievers do occasionally appear in
the 1st (injury, ejection) — about 0.4% of half-innings — so they get rows
too, flagged ``is_starter=False``.

Runs allowed
------------
Statcast carries the batting team's score before and after every pitch, so
runs are attributed to whoever was actually on the mound rather than assumed
to belong to the starter.

Those score columns can't be trusted row-by-row, though: ``post_bat_score``
occasionally fails to reflect a run that just scored, and the run only shows
up in the *next* plate appearance's ``bat_score`` (see game 747132 on
2024-04-24, where a run-scoring single reads 0 -> 0). Differencing each row
in isolation silently drops those runs. So the score is tracked as a running
maximum across the half-inning instead, which recovers the run one row late
— still within the same pitcher's outing, since pitching changes never
happen mid-plate-appearance.

Note this counts *all* runs, not earned runs — Statcast doesn't mark
earned/unearned. That's not a compromise here: the NRFI label counts
unearned runs too, so runs allowed is the better-aligned stat anyway. The
features are named accordingly (``runs_1st``, not ``era_1st``).

Run it:
    python -m app.collection.statcast_boxscore --start 2018-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

from app.collection.mlb_stats import mlb_today
from app.collection.statcast_backfill import (
    DEFAULT_DATA_DIR,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_WAIT,
    StatcastBackfillError,
    _month_chunks,
    fetch_statcast_chunk,
)

# Statcast's `events` vocabulary, grouped into the counting stats we need.
# `events` is only set on the last pitch of a plate appearance, so counting
# rows that match is equivalent to counting plate appearances.
HIT_EVENTS = frozenset({"single", "double", "triple", "home_run"})
WALK_EVENTS = frozenset({"walk", "intent_walk"})
STRIKEOUT_EVENTS = frozenset({"strikeout", "strikeout_double_play"})
HOME_RUN_EVENTS = frozenset({"home_run"})

PITCHER_COLUMNS = [
    "game_pk",
    "game_date",
    "pitcher_id",
    "pitcher_name",
    "throws",
    "team_abbr",
    "is_home",
    "is_starter",
    "batters_faced_1st",
    "hits_1st",
    "runs_1st",
    "walks_1st",
    "strikeouts_1st",
    "home_runs_1st",
    "pitches_1st",
]

TEAM_COLUMNS = [
    "game_pk",
    "game_date",
    "team_abbr",
    "is_home",
    "runs_1st",
    "hits_1st",
    "walks_1st",
    "strikeouts_1st",
    "batters_1st",
]

PITCHER_PARQUET = "pitcher_first_inning.parquet"
TEAM_PARQUET = "team_first_inning.parquet"


def _empty_outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        pd.DataFrame(columns=PITCHER_COLUMNS),
        pd.DataFrame(columns=TEAM_COLUMNS),
    )


def derive_first_inning_stats(
    df: pd.DataFrame, regular_season_only: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse pitch-level rows into (pitcher lines, team lines) for the 1st."""
    if df.empty:
        return _empty_outputs()

    data = df
    if regular_season_only and "game_type" in data.columns:
        data = data[data["game_type"] == "R"]

    first = data[data["inning"] == 1].copy()
    if first.empty:
        return _empty_outputs()

    # Top of the 1st = away team batting, home team pitching.
    first["batting_is_home"] = first["inning_topbot"].str.lower().str[:3] == "bot"
    first["batting_team"] = first["home_team"].where(
        first["batting_is_home"], first["away_team"]
    )
    first["pitching_team"] = first["away_team"].where(
        first["batting_is_home"], first["home_team"]
    )

    first["events"] = first["events"].fillna("")
    first["is_hit"] = first["events"].isin(HIT_EVENTS)
    first["is_walk"] = first["events"].isin(WALK_EVENTS)
    first["is_strikeout"] = first["events"].isin(STRIKEOUT_EVENTS)
    first["is_home_run"] = first["events"].isin(HOME_RUN_EVENTS)

    first = first.sort_values(
        ["game_pk", "inning_topbot", "at_bat_number", "pitch_number"]
    )
    first["runs"] = _runs_per_pitch(first)

    return _pitcher_lines(first), _team_lines(first)


def _runs_per_pitch(first: pd.DataFrame) -> pd.Series:
    """Runs scored on each pitch, robust to Statcast's lagging score updates.

    Takes the running maximum of the batting team's score across the
    half-inning, so a run that a row fails to report is still picked up from
    the following row. Differencing that monotone series gives back per-pitch
    runs whose sum is always the half-inning's true total.
    """
    scores = first[["bat_score", "post_bat_score"]].apply(
        pd.to_numeric, errors="coerce"
    )
    running = (
        scores.max(axis=1)
        .fillna(0)
        .groupby([first["game_pk"], first["inning_topbot"]])
        .cummax()
    )

    half = [first["game_pk"], first["inning_topbot"]]
    # First pitch of the half: runs relative to the score the half opened at.
    opening = scores["bat_score"].fillna(0).groupby(half).transform("first")
    return running.groupby(half).diff().fillna(running - opening)


def _format_name(name: object) -> str | None:
    """Statcast writes the pitcher as "Last, First"; store it read-order."""
    if not isinstance(name, str) or not name.strip():
        return None
    last, _, rest = name.partition(",")
    return f"{rest.strip()} {last.strip()}".strip() if rest else name.strip()


def _pitcher_lines(first: pd.DataFrame) -> pd.DataFrame:
    lines = (
        first.groupby(["game_pk", "inning_topbot", "pitcher"], sort=False)
        .agg(
            game_date=("game_date", "first"),
            pitcher_name=("player_name", "first"),
            throws=("p_throws", "first"),
            team_abbr=("pitching_team", "first"),
            is_home=("batting_is_home", "first"),
            batters_faced_1st=("at_bat_number", "nunique"),
            hits_1st=("is_hit", "sum"),
            runs_1st=("runs", "sum"),
            walks_1st=("is_walk", "sum"),
            strikeouts_1st=("is_strikeout", "sum"),
            home_runs_1st=("is_home_run", "sum"),
            pitches_1st=("pitch_number", "size"),
        )
        .reset_index()
    )

    # The pitching team is home exactly when the batting team is not.
    lines["is_home"] = ~lines["is_home"]

    # Whoever threw the half-inning's first pitch started it; anyone else who
    # appears came on in relief.
    starters = (
        first.groupby(["game_pk", "inning_topbot"], sort=False)["pitcher"]
        .first()
        .rename("starter")
        .reset_index()
    )
    lines = lines.merge(starters, on=["game_pk", "inning_topbot"], how="left")
    lines["is_starter"] = lines["pitcher"] == lines["starter"]

    lines = lines.rename(columns={"pitcher": "pitcher_id"})
    lines["pitcher_name"] = lines["pitcher_name"].map(_format_name)
    return _finalize(lines, PITCHER_COLUMNS, ["pitcher_id"])


def _team_lines(first: pd.DataFrame) -> pd.DataFrame:
    lines = (
        first.groupby(["game_pk", "inning_topbot"], sort=False)
        .agg(
            game_date=("game_date", "first"),
            team_abbr=("batting_team", "first"),
            is_home=("batting_is_home", "first"),
            runs_1st=("runs", "sum"),
            hits_1st=("is_hit", "sum"),
            walks_1st=("is_walk", "sum"),
            strikeouts_1st=("is_strikeout", "sum"),
            batters_1st=("at_bat_number", "nunique"),
        )
        .reset_index()
    )
    return _finalize(lines, TEAM_COLUMNS, [])


def _finalize(
    lines: pd.DataFrame, columns: list[str], extra_int_cols: list[str]
) -> pd.DataFrame:
    lines["game_pk"] = lines["game_pk"].astype("int64")
    lines["game_date"] = pd.to_datetime(lines["game_date"])
    lines["is_home"] = lines["is_home"].astype(bool)

    count_cols = [
        c
        for c in columns
        if c.endswith("_1st") or c in extra_int_cols
    ]
    for col in count_cols:
        lines[col] = pd.to_numeric(lines[col], errors="coerce").fillna(0).astype(int)

    return lines[columns].sort_values(["game_pk"]).reset_index(drop=True)


def run_derivation(
    start: dt.date,
    end: dt.date,
    data_dir: Path = DEFAULT_DATA_DIR,
    regular_season_only: bool = True,
    force: bool = False,
    retries: int = DEFAULT_RETRIES,
    retry_wait: float = DEFAULT_RETRY_WAIT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Derive first-inning box scores for a date range and merge them to disk.

    Reads the same month-chunked cache the M2 backfill built, so a range
    that's already been backfilled costs no network at all. Processes one
    chunk at a time to keep the multi-GB pitch dataset out of memory.
    """
    raw_dir = data_dir / "raw" / "statcast"
    processed_dir = data_dir / "processed"

    chunks = _month_chunks(start, end)
    pitcher_frames: list[pd.DataFrame] = []
    team_frames: list[pd.DataFrame] = []

    for i, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        df = fetch_statcast_chunk(
            chunk_start, chunk_end, raw_dir, force, retries, retry_wait
        )
        pitchers, teams = derive_first_inning_stats(df, regular_season_only)
        del df  # release the month's pitch data before the next chunk
        if not pitchers.empty:
            pitcher_frames.append(pitchers)
        if not teams.empty:
            team_frames.append(teams)
        print(
            f"  [{i}/{len(chunks)}] {chunk_start}..{chunk_end}: "
            f"{len(pitchers)} pitcher lines, {len(teams)} team lines"
        )

    pitchers = (
        pd.concat(pitcher_frames, ignore_index=True)
        if pitcher_frames
        else pd.DataFrame(columns=PITCHER_COLUMNS)
    )
    teams = (
        pd.concat(team_frames, ignore_index=True)
        if team_frames
        else pd.DataFrame(columns=TEAM_COLUMNS)
    )

    processed_dir.mkdir(parents=True, exist_ok=True)
    pitchers = _merge_to_disk(
        pitchers,
        processed_dir / PITCHER_PARQUET,
        keys=["game_pk", "pitcher_id"],
    )
    teams = _merge_to_disk(
        teams, processed_dir / TEAM_PARQUET, keys=["game_pk", "team_abbr"]
    )
    return pitchers, teams


def _merge_to_disk(
    new: pd.DataFrame, path: Path, keys: list[str]
) -> pd.DataFrame:
    """Merge freshly derived rows into the stored dataset, deduped by ``keys``."""
    if path.exists():
        combined = pd.concat([pd.read_parquet(path), new], ignore_index=True)
    else:
        combined = new

    combined = (
        combined.drop_duplicates(subset=keys, keep="last")
        .sort_values(keys)
        .reset_index(drop=True)
    )
    combined.to_parquet(path, index=False)
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
        description="Derive first-inning box scores from cached Statcast data."
    )
    parser.add_argument("--start", default="2018-01-01", help="Start (YYYY-MM-DD).")
    parser.add_argument(
        "--end",
        default=mlb_today().isoformat(),
        help="End (YYYY-MM-DD). Defaults to today (US Eastern).",
    )
    parser.add_argument(
        "--data-dir", default=str(DEFAULT_DATA_DIR), help="Data directory."
    )
    parser.add_argument(
        "--include-postseason",
        action="store_true",
        help="Include non-regular-season games.",
    )
    args = parser.parse_args(argv)

    try:
        pitchers, teams = run_derivation(
            _parse_date(args.start),
            _parse_date(args.end),
            data_dir=Path(args.data_dir),
            regular_season_only=not args.include_postseason,
        )
    except StatcastBackfillError as exc:
        print(f"ERROR: {exc}")
        return 1

    starters = int(pitchers["is_starter"].sum()) if not pitchers.empty else 0
    print(
        f"First-inning box scores derived for {args.start}..{args.end}.\n"
        f"  Pitcher lines: {len(pitchers)} ({starters} starters)\n"
        f"  Team lines:    {len(teams)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
