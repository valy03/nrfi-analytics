"""Feature pipeline (M4): database in, feature matrix out.

The training matrix and a single game's inference row come from the *same*
call. ``compute_features`` is always run over the full history, and the
caller's filter is applied to the result afterwards — so there is one code
path, and "the features we trained on" and "the features we predict from"
can't drift apart. Filtering earlier would be faster and would quietly
reintroduce the asymmetry this milestone exists to avoid.

The full history is ~18k games and builds in a couple of seconds, so the
simplicity is close to free. The matrix is cached to parquet for M5 to train
against.

Run it:
    python -m app.features.pipeline                    # build + cache
    python -m app.features.pipeline --date 2026-08-05  # inspect one slate
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collection.mlb_stats import mlb_today
from app.db.session import session_scope
from app.features import config as cfg
from app.features.compute import compute_features

DEFAULT_MATRIX_PATH = Path("data/processed/features.parquet")

# The starter is normally read from the observed box score. For a game that
# hasn't been played there is no box score, so we fall back to the announced
# probable — which is exactly what's available at prediction time.
_GAMES_SQL = text(
    """
    SELECT g.game_pk,
           g.game_date,
           g.season,
           g.home_team_id,
           g.away_team_id,
           g.nrfi,
           COALESCE(hs.pitcher_id, g.home_probable_pitcher_id) AS home_sp_id,
           COALESCE(aws.pitcher_id, g.away_probable_pitcher_id) AS away_sp_id
      FROM games g
      LEFT JOIN pitcher_game_stats hs
             ON hs.game_pk = g.game_pk AND hs.is_starter AND hs.is_home
      LEFT JOIN pitcher_game_stats aws
             ON aws.game_pk = g.game_pk AND aws.is_starter AND NOT aws.is_home
     WHERE g.game_type = 'R'
    """
)

_TEAM_LINES_SQL = text(
    """
    SELECT s.game_pk, g.game_date, s.team_id, s.is_home,
           s.runs_1st, s.strikeouts_1st, s.batters_1st
      FROM team_game_stats s
      JOIN games g ON g.game_pk = s.game_pk
     WHERE g.game_type = 'R'
    """
)

_PITCHER_LINES_SQL = text(
    """
    SELECT s.game_pk, g.game_date, s.pitcher_id,
           s.runs_1st, s.hits_1st, s.walks_1st,
           s.strikeouts_1st, s.batters_faced_1st
      FROM pitcher_game_stats s
      JOIN games g ON g.game_pk = s.game_pk
     WHERE s.is_starter AND g.game_type = 'R'
    """
)


class FeaturePipelineError(RuntimeError):
    """Raised when the feature matrix can't be built."""


def load_inputs(session: Session) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read games and observed first-inning lines out of Postgres."""
    connection = session.connection()
    games = pd.read_sql(_GAMES_SQL, connection)
    if games.empty:
        raise FeaturePipelineError(
            "No games in the database. Run the M3 load first: "
            "python -m app.ingestion.historical"
        )
    team_lines = pd.read_sql(_TEAM_LINES_SQL, connection)
    pitcher_lines = pd.read_sql(_PITCHER_LINES_SQL, connection)
    if team_lines.empty or pitcher_lines.empty:
        raise FeaturePipelineError(
            "No first-inning box scores. Derive and load them first: "
            "python -m app.collection.statcast_boxscore && "
            "python -m app.ingestion.game_stats"
        )
    return games, team_lines, pitcher_lines


def build_full_matrix(session: Session) -> pd.DataFrame:
    """Features for every regular-season game on record, labeled or not."""
    games, team_lines, pitcher_lines = load_inputs(session)
    return compute_features(games, team_lines, pitcher_lines)


def build_training_matrix(
    session: Session, seasons: list[int] | None = None
) -> pd.DataFrame:
    """The labeled subset — what M5 trains and evaluates on."""
    matrix = build_full_matrix(session)
    matrix = matrix[matrix[cfg.TARGET_COLUMN].notna()].copy()
    if seasons:
        matrix = matrix[matrix["season"].isin(seasons)]
    matrix[cfg.TARGET_COLUMN] = matrix[cfg.TARGET_COLUMN].astype(int)
    return matrix.reset_index(drop=True)


def features_for_games(
    session: Session, game_pks: list[int]
) -> pd.DataFrame:
    """Feature rows for specific games — the inference path.

    Works for games that haven't been played: they come back with a full
    feature row and a null target.
    """
    matrix = build_full_matrix(session)
    return matrix[matrix["game_pk"].isin(game_pks)].reset_index(drop=True)


def features_for_date(
    session: Session, date: str | dt.date | None = None
) -> pd.DataFrame:
    """Feature rows for a date's slate — what the M7 job will call."""
    if date is None:
        date = mlb_today()
    if isinstance(date, str):
        date = dt.date.fromisoformat(date)

    matrix = build_full_matrix(session)
    target = pd.Timestamp(date)
    return matrix[matrix["game_date"] == target].reset_index(drop=True)


def save_matrix(matrix: pd.DataFrame, path: Path = DEFAULT_MATRIX_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_parquet(path, index=False)
    return path


def describe(matrix: pd.DataFrame) -> str:
    """A short report — the M4 exit criteria at a glance."""
    feature_cols = [c for c in cfg.FEATURE_COLUMNS if c in matrix.columns]
    nulls = matrix[feature_cols].isna().sum()
    offenders = nulls[nulls > 0]

    lines = [
        f"  Rows:     {len(matrix)}",
        f"  Features: {len(feature_cols)}",
        f"  Seasons:  {matrix['season'].min()}-{matrix['season'].max()}",
    ]
    if cfg.TARGET_COLUMN in matrix.columns:
        labeled = matrix[cfg.TARGET_COLUMN].notna().sum()
        lines.append(f"  Labeled:  {labeled} ({len(matrix) - labeled} unlabeled)")
        if labeled:
            rate = matrix[cfg.TARGET_COLUMN].mean()
            lines.append(f"  NRFI:     {rate:.1%}")
    lines.append(
        "  NaNs:     none"
        if offenders.empty
        else f"  NaNs:     {offenders.to_dict()}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the NRFI feature matrix."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_MATRIX_PATH),
        help="Where to write the training matrix.",
    )
    parser.add_argument(
        "--date",
        help="Inspect one date's slate instead of building the matrix.",
    )
    parser.add_argument(
        "--season", type=int, action="append", help="Limit to season(s)."
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Report only; don't write."
    )
    args = parser.parse_args(argv)

    try:
        with session_scope() as session:
            if args.date:
                slate = features_for_date(session, args.date)
                if slate.empty:
                    print(f"No games on {args.date}.")
                    return 0
                print(f"Feature rows for {args.date}:\n{describe(slate)}\n")
                preview = [
                    "game_pk",
                    "home_sp_nrfi_rate",
                    "away_sp_nrfi_rate",
                    "home_team_scored_1st_rate",
                    "away_team_scored_1st_rate",
                    "park_nrfi_rate",
                ]
                print(slate[preview].round(3).to_string(index=False))
                return 0

            matrix = build_training_matrix(session, args.season)
    except FeaturePipelineError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Feature matrix built.\n{describe(matrix)}")
    if not args.no_save:
        path = save_matrix(matrix, Path(args.output))
        print(f"  Written:  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
