"""Grade predictions against known outcomes (M8 prerequisite).

No prior milestone owns this: M7 stores predictions before a game is
played, and M1/M3's daily loader labels a game's first-inning outcome once
it's final — but nothing connects the two. M8's "historical results +
accuracy" endpoints can't honestly report a win rate without it, so it's a
straightforward join, not a new data source: every input already exists in
Postgres.

A prediction is gradeable once its game has a known outcome
(``games.nrfi is not None``) and doesn't already have a ``PredictionResult``
— that second check is what makes re-running this safe: yesterday's already
graded predictions are skipped, and a fresh run only picks up games that
finished since the last pass.

``odds_american`` / ``stake`` / ``profit`` are left null — there's no odds
source wired up yet (deferred per docs/milestones.md M8), so ROI isn't
computable. Accuracy and win rate don't depend on them.

Run it:
    python -m app.grading.results                  # everything ungraded
    python -m app.grading.results --date 2026-08-18
"""

from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import session_scope
from app.models import Game, Prediction, PredictionResult
from app.models.prediction import NRFI, YRFI


def _ungraded(session: Session, date: dt.date | None) -> list[tuple[Prediction, bool]]:
    """(prediction, nrfi) pairs for finished games with no result yet."""
    query = (
        select(Prediction, Game.nrfi)
        .join(Game, Game.game_pk == Prediction.game_pk)
        .outerjoin(
            PredictionResult, PredictionResult.prediction_id == Prediction.id
        )
        .where(Game.nrfi.is_not(None), PredictionResult.id.is_(None))
    )
    if date is not None:
        query = query.where(Game.game_date == date)
    return list(session.execute(query).all())


def grade_predictions(session: Session, date: dt.date | None = None) -> int:
    """Create a ``PredictionResult`` for every gradeable prediction. Returns
    the number graded.
    """
    graded = 0
    for prediction, nrfi in _ungraded(session, date):
        actual_label = NRFI if nrfi else YRFI
        session.add(
            PredictionResult(
                prediction_id=prediction.id,
                game_pk=prediction.game_pk,
                actual_label=actual_label,
                correct=(actual_label == prediction.predicted_label),
            )
        )
        graded += 1
    session.flush()
    return graded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Grade stored predictions against now-known game outcomes."
    )
    parser.add_argument(
        "--date", help="Limit to one date (YYYY-MM-DD). Default: everything ungraded."
    )
    args = parser.parse_args(argv)

    date = dt.date.fromisoformat(args.date) if args.date else None
    with session_scope() as session:
        graded = grade_predictions(session, date)

    print(f"Graded {graded} prediction(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
