"""M5 — Logistic Regression baseline.

Trains one interpretable model on the M4 feature matrix and evaluates it on
a season it has never seen. Reporting itself (naive references, pass/fail
criteria) lives in app.training.report — shared with M6's XGBoost candidate
so the two are graded through the exact same path.

Run it:
    python -m app.training.baseline                    # build/load + train + report
    python -m app.training.baseline --matrix path.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.features import config as fcfg
from app.features.pipeline import DEFAULT_MATRIX_PATH
from app.training import config as cfg
from app.training.data import load_matrix
from app.training.report import beats_references, build_report, describe, passed
from app.training.split import time_based_split


def train_baseline(train: pd.DataFrame) -> Pipeline:
    """Logistic Regression, scaled — the features span very different ranges
    (rates in [0, 1] vs. prior-start counts in the hundreds), and unscaled
    inputs would let the raw count columns dominate the fit for no reason
    tied to their actual predictive value.
    """
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "logreg",
                LogisticRegression(max_iter=1000, random_state=cfg.RANDOM_STATE),
            ),
        ]
    )
    model.fit(train[fcfg.FEATURE_COLUMNS], train[fcfg.TARGET_COLUMN])
    return model


def save_artifacts(model: Pipeline, report: dict, criteria: dict) -> None:
    cfg.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, cfg.MODEL_PATH)
    cfg.METRICS_PATH.write_text(json.dumps({**report, "criteria": criteria}, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the M5 Logistic Regression baseline."
    )
    parser.add_argument(
        "--matrix",
        default=str(DEFAULT_MATRIX_PATH),
        help="Feature matrix parquet (built via app.features.pipeline if missing).",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Report only; don't write artifacts."
    )
    args = parser.parse_args(argv)

    matrix = load_matrix(Path(args.matrix))
    train, test = time_based_split(matrix)
    if train.empty or test.empty:
        print("ERROR: train or test split is empty — check TEST_SEASON_CUTOFF.")
        return 1

    model = train_baseline(train)
    report = build_report(model, cfg.MODEL_NAME, cfg.MODEL_VERSION, train, test)

    print(f"M5 baseline — {cfg.MODEL_VERSION}\n{describe(report)}")
    criteria = beats_references(report)
    ok = passed(criteria)
    print(
        f"\n  Beats majority-class accuracy: {criteria['beats_majority_accuracy']}\n"
        f"  Ranks better than chance (AUC>0.5): {criteria['ranks_better_than_chance']}\n"
        f"  Beats league-average log loss: {criteria['beats_league_log_loss']}"
        " (reported, not gating — see report.beats_references docstring)\n"
        f"  M5 exit criterion: {'PASS' if ok else 'FAIL'}"
    )

    if not args.no_save:
        save_artifacts(model, report, criteria)
        print(f"  Model:    {cfg.MODEL_PATH}")
        print(f"  Metrics:  {cfg.METRICS_PATH}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
