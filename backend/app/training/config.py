"""M5 training configuration.

Constants live here for the same reason as ``app/features/config.py``: the
knobs that shape evaluation should be visible in one place, not buried in the
training script.
"""

from __future__ import annotations

from pathlib import Path

RANDOM_STATE = 42

# Seasons before this year train the model; this year and later are held out
# for evaluation. A genuinely future season is the only honest test of
# whether the model generalizes forward — which is the actual deployment
# scenario (predict a season the model has never seen). See split.py.
TEST_SEASON_CUTOFF = 2024

MODEL_DIR = Path("data/models")

MODEL_NAME = "logistic_regression_baseline"
MODEL_VERSION = "m5-v1"
MODEL_PATH = MODEL_DIR / f"{MODEL_VERSION}.joblib"
METRICS_PATH = MODEL_DIR / f"{MODEL_VERSION}_metrics.json"
