"""M6 — XGBoost candidate.

Same feature list, same time-based split, same reporting path as M5's
Logistic Regression (app.training.report) — the only thing that changes is
the model, which is what makes the M6 head-to-head comparison
(app.training.compare) a fair one.

Tree count is picked by early stopping against an internal validation slice
carved from the *training* seasons — never the M5/M6 held-out test set. If
the test set picked the tree count too, the reported test metrics would be
optimistic by exactly the amount of tuning that happened against them, the
same asymmetry the M4 as-of joins exist to rule out for features. Once the
tree count is fixed, the final model refits on the *full* training set
(including the validation slice) at that fixed size — no early stopping —
so the artifact actually shipped doesn't waste the validation seasons' data.

Run it:
    python -m app.training.xgboost_model
    python -m app.training.xgboost_model --matrix path.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
import xgboost as xgb

from app.features import config as fcfg
from app.features.pipeline import DEFAULT_MATRIX_PATH
from app.training import config as cfg
from app.training.data import load_matrix
from app.training.report import beats_references, build_report, describe, passed
from app.training.split import time_based_split


def _xgb_params() -> dict:
    return dict(
        max_depth=3,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        eval_metric="logloss",
        random_state=cfg.RANDOM_STATE,
    )


def train_xgboost(train: pd.DataFrame) -> xgb.XGBClassifier:
    seasons = sorted(train["season"].unique())
    if len(seasons) < 2:
        raise ValueError(
            "Need at least two training seasons: one to fit, one to hold out "
            "for early-stopping validation."
        )
    val_season = seasons[-1]
    fit_train = train[train["season"] < val_season]
    fit_val = train[train["season"] == val_season]

    probe = xgb.XGBClassifier(
        n_estimators=cfg.XGB_MAX_ESTIMATORS,
        early_stopping_rounds=cfg.XGB_EARLY_STOPPING_ROUNDS,
        **_xgb_params(),
    )
    probe.fit(
        fit_train[fcfg.FEATURE_COLUMNS],
        fit_train[fcfg.TARGET_COLUMN],
        eval_set=[(fit_val[fcfg.FEATURE_COLUMNS], fit_val[fcfg.TARGET_COLUMN])],
        verbose=False,
    )
    best_n = probe.best_iteration + 1

    final = xgb.XGBClassifier(n_estimators=best_n, **_xgb_params())
    final.fit(train[fcfg.FEATURE_COLUMNS], train[fcfg.TARGET_COLUMN])
    return final


def save_artifacts(model: xgb.XGBClassifier, report: dict, criteria: dict) -> None:
    cfg.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, cfg.XGB_MODEL_PATH)
    cfg.XGB_METRICS_PATH.write_text(
        json.dumps({**report, "criteria": criteria}, indent=2)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the M6 XGBoost candidate."
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

    model = train_xgboost(train)
    report = build_report(model, cfg.XGB_MODEL_NAME, cfg.XGB_MODEL_VERSION, train, test)

    print(f"M6 XGBoost candidate — {cfg.XGB_MODEL_VERSION}\n{describe(report)}")
    criteria = beats_references(report)
    ok = passed(criteria)
    print(f"\n  Beats naive references: {'PASS' if ok else 'FAIL'}")

    if not args.no_save:
        save_artifacts(model, report, criteria)
        print(f"  Model:    {cfg.XGB_MODEL_PATH}")
        print(f"  Metrics:  {cfg.XGB_METRICS_PATH}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
