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

# --- M5: Logistic Regression baseline ---------------------------------
MODEL_NAME = "logistic_regression_baseline"
MODEL_VERSION = "m5-v1"
MODEL_PATH = MODEL_DIR / f"{MODEL_VERSION}.joblib"
METRICS_PATH = MODEL_DIR / f"{MODEL_VERSION}_metrics.json"

# --- M6: XGBoost candidate ---------------------------------------------
XGB_MODEL_NAME = "xgboost"
XGB_MODEL_VERSION = "m6-xgb-v1"
XGB_MODEL_PATH = MODEL_DIR / f"{XGB_MODEL_VERSION}.joblib"
XGB_METRICS_PATH = MODEL_DIR / f"{XGB_MODEL_VERSION}_metrics.json"

# Early stopping probes up to this many trees, watched against an internal
# validation slice carved from the *training* seasons only (see
# xgboost_model.py) — the M5/M6 held-out test set is never used to pick the
# tree count, only to grade the final result.
XGB_MAX_ESTIMATORS = 1000
XGB_EARLY_STOPPING_ROUNDS = 30

# --- M6: champion ---------------------------------------------------------
# Whichever of the above compare.py selects — this is the one artifact M7
# actually loads for daily inference, so it doesn't need to know which
# family of model is currently in production.
CHAMPION_PATH = MODEL_DIR / "champion.joblib"
CHAMPION_METRICS_PATH = MODEL_DIR / "champion_metrics.json"
COMPARISON_PATH = MODEL_DIR / "m6_comparison.json"
