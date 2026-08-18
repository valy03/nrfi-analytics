"""M7 — persist predictions (M3 schema).

A thin wrapper over the same ``upsert_rows`` every M3/M4 loader uses, keyed
on ``(game_pk, model_version)`` to match ``Prediction``'s unique constraint.
Re-running the job for a slate it already predicted updates those rows in
place; a *new* model version (a fresh M6 champion) adds new rows alongside
the old ones instead of overwriting them, which is what lets M11 compare
accuracy across model versions without rewriting history.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Prediction


def save_predictions(session: Session, rows: list[dict]) -> UpsertCounts:
    return upsert_rows(session, Prediction, rows, key_cols=["game_pk", "model_version"])
