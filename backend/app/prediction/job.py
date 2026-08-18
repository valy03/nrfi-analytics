"""M7 — daily prediction job.

Ties M1 (schedule), M3 (storage), M4 (features), and M6 (champion model)
into the thing that actually runs every morning: refresh today's slate,
compute features for whatever's ready to predict, run the champion model,
store the results.

"Ready to predict" is narrower than "on today's slate". A game only
qualifies once both starters are announced — a shrunk league-average
placeholder standing in for an unannounced starter isn't a real prediction,
it's a guess dressed up as one, and every training row had a real starter
attached — and only while it hasn't started yet (requirements.md: the
application shall not predict live games). Games that don't qualify are
skipped and counted, not silently dropped: this job runs unattended, so a
skip nobody notices is a bug nobody notices either.

Run it:
    python -m app.prediction.job                    # today, US Eastern
    python -m app.prediction.job --date 2026-08-05
"""

from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collection.mlb_stats import MLBStatsAPIError, mlb_today
from app.db.session import session_scope
from app.features.pipeline import FeaturePipelineError, features_for_games
from app.ingestion.daily import DailyIngestionError, load_date
from app.models import Game
from app.prediction.infer import ChampionNotFoundError, predict
from app.prediction.store import save_predictions

# Statuses meaning the game genuinely hasn't started. Anything else — in
# progress, final, postponed, suspended, ... — is skipped, so the job never
# generates a "prediction" for a game already underway or decided. This is
# an allowlist rather than a blocklist on purpose: an MLB status string we
# don't recognize should default to "don't predict it", not the reverse.
PENDING_STATUSES = {"Scheduled", "Pre-Game", "Warmup", "Delayed Start", "Delayed"}


def eligible_games(session: Session, date: dt.date) -> tuple[list[int], int, int]:
    """This date's regular-season games safe to predict.

    Returns (game_pks, skipped_started, skipped_no_starters).
    """
    rows = session.execute(
        select(
            Game.game_pk,
            Game.status,
            Game.home_probable_pitcher_id,
            Game.away_probable_pitcher_id,
        ).where(Game.game_date == date, Game.game_type == "R")
    ).all()

    game_pks: list[int] = []
    skipped_started = skipped_no_starters = 0
    for game_pk, status, home_sp, away_sp in rows:
        if status not in PENDING_STATUSES:
            skipped_started += 1
            continue
        if home_sp is None or away_sp is None:
            skipped_no_starters += 1
            continue
        game_pks.append(game_pk)

    return game_pks, skipped_started, skipped_no_starters


def run(session: Session, date: dt.date | None = None) -> dict:
    date = date or mlb_today()

    load_date(session, date)  # M1 -> M3: refresh schedule, pitchers, games

    game_pks, skipped_started, skipped_no_starters = eligible_games(session, date)
    result = {
        "date": date.isoformat(),
        "eligible": len(game_pks),
        "skipped_started": skipped_started,
        "skipped_no_starters": skipped_no_starters,
        "predicted": 0,
    }
    if not game_pks:
        return result

    matrix = features_for_games(session, game_pks)
    rows = predict(matrix)
    counts = save_predictions(session, rows)

    result["predicted"] = len(rows)
    result["upsert"] = str(counts)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the M7 daily prediction job.")
    parser.add_argument(
        "--date", help="Date to predict (YYYY-MM-DD). Default: today (US Eastern)."
    )
    args = parser.parse_args(argv)

    date = dt.date.fromisoformat(args.date) if args.date else None
    try:
        with session_scope() as session:
            result = run(session, date)
    except (
        DailyIngestionError,
        FeaturePipelineError,
        ChampionNotFoundError,
        MLBStatsAPIError,
        ValueError,
    ) as exc:
        # The "logging/alerting on job failure" deliverable — deliberately
        # not fancy for the MVP, matching every other M1-M6 CLI's error
        # reporting. A scheduler wraps this and treats a non-zero exit /
        # this stderr line as the failure signal.
        print(f"ERROR: prediction job failed for {date or 'today'}: {exc}")
        return 1

    print(
        f"Prediction job complete for {result['date']}.\n"
        f"  Eligible:  {result['eligible']}\n"
        f"  Skipped:   {result['skipped_started']} already started/finished, "
        f"{result['skipped_no_starters']} missing an announced starter\n"
        f"  Predicted: {result['predicted']}"
        + (f"\n  {result['upsert']}" if "upsert" in result else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
