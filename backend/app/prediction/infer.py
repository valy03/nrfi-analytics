"""M7 — champion inference: feature rows in, prediction rows out.

Deliberately reads the champion artifact fresh on every call rather than
caching it in memory. This job runs once a day, not on a hot request path,
so the cost of a re-read is nothing — and it means a fresh
``python -m app.training.compare`` run takes effect on the job's next
invocation automatically, with no service restart or cache-bust required.
"""

from __future__ import annotations

import json

import joblib
import pandas as pd

from app.features import config as fcfg
from app.training import config as tcfg


class ChampionNotFoundError(RuntimeError):
    """Raised when M6 hasn't produced a champion artifact yet."""


def load_champion() -> tuple[object, str, str]:
    if not tcfg.CHAMPION_PATH.exists():
        raise ChampionNotFoundError(
            f"No champion model at {tcfg.CHAMPION_PATH}. Run "
            "`python -m app.training.compare` first."
        )
    model = joblib.load(tcfg.CHAMPION_PATH)
    metadata = json.loads(tcfg.CHAMPION_METRICS_PATH.read_text())
    return model, metadata["model_name"], metadata["model_version"]


def predict(matrix: pd.DataFrame) -> list[dict]:
    """One prediction payload per row of ``matrix`` — ready for
    ``app.prediction.store.save_predictions``.

    ``confidence`` is distance from a coin flip rescaled to 0-1 (0 at
    p=0.5, 1 at a certain p=0 or p=1), matching the column's contract in
    ``app.models.prediction``. ``features`` is a snapshot of the exact
    inputs the model saw, so a prediction stays explainable even after the
    feature pipeline moves on.
    """
    if matrix.empty:
        return []

    model, model_name, model_version = load_champion()
    proba = model.predict_proba(matrix[fcfg.FEATURE_COLUMNS])[:, 1]
    feature_rows = matrix[fcfg.FEATURE_COLUMNS].to_dict("records")

    rows = []
    for game_pk, p, features in zip(matrix["game_pk"], proba, feature_rows):
        p = float(p)
        rows.append(
            {
                "game_pk": int(game_pk),
                "model_name": model_name,
                "model_version": model_version,
                "predicted_label": "NRFI" if p >= 0.5 else "YRFI",
                "nrfi_probability": p,
                "yrfi_probability": 1.0 - p,
                "confidence": abs(2.0 * p - 1.0),
                "features": {k: float(v) for k, v in features.items()},
            }
        )
    return rows
