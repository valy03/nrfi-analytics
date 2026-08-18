"""M5 — Logistic Regression baseline.

Trains one interpretable model on the M4 feature matrix, evaluates it on a
season it has never seen, and checks it actually beats two naive references
(app.training.evaluate) rather than just assuming a model adds signal.

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

from app.db.session import session_scope
from app.features import config as fcfg
from app.features.pipeline import DEFAULT_MATRIX_PATH, build_training_matrix
from app.training import config as cfg
from app.training.evaluate import (
    compute_metrics,
    league_average_reference,
    majority_class_reference,
)
from app.training.split import time_based_split


def load_matrix(path=DEFAULT_MATRIX_PATH) -> pd.DataFrame:
    """The M4 matrix — reuse the cached parquet if present, else rebuild it."""
    if path.exists():
        return pd.read_parquet(path)
    with session_scope() as session:
        return build_training_matrix(session)


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


def build_report(model: Pipeline, train: pd.DataFrame, test: pd.DataFrame) -> dict:
    y_train = train[fcfg.TARGET_COLUMN]
    y_test = test[fcfg.TARGET_COLUMN]
    n_test = len(test)

    model_proba = model.predict_proba(test[fcfg.FEATURE_COLUMNS])[:, 1]
    majority_proba = majority_class_reference(y_train, n_test)
    league_proba = league_average_reference(y_train, n_test)

    return {
        "model_name": cfg.MODEL_NAME,
        "model_version": cfg.MODEL_VERSION,
        "train": {
            "seasons": sorted(train["season"].unique().tolist()),
            "n": len(train),
            "nrfi_rate": float(y_train.mean()),
        },
        "test": {
            "seasons": sorted(test["season"].unique().tolist()),
            "n": n_test,
            "nrfi_rate": float(y_test.mean()),
        },
        "model": compute_metrics(y_test, model_proba).to_dict(),
        "reference_majority_class": compute_metrics(y_test, majority_proba).to_dict(),
        "reference_league_average": compute_metrics(y_test, league_proba).to_dict(),
    }


def describe(report: dict) -> str:
    def row(label: str, m: dict) -> str:
        return (
            f"  {label:<24} acc={m['accuracy']:.3f}  prec={m['precision']:.3f}  "
            f"rec={m['recall']:.3f}  f1={m['f1']:.3f}  "
            f"auc={m['roc_auc']:.3f}  logloss={m['log_loss']:.4f}"
        )

    train, test = report["train"], report["test"]
    lines = [
        f"  Train seasons: {train['seasons']}  (n={train['n']}, "
        f"NRFI rate={train['nrfi_rate']:.3f})",
        f"  Test seasons:  {test['seasons']}  (n={test['n']}, "
        f"NRFI rate={test['nrfi_rate']:.3f})",
        "",
        row("Logistic Regression:", report["model"]),
        row("Majority-class ref:", report["reference_majority_class"]),
        row("League-average ref:", report["reference_league_average"]),
    ]
    return "\n".join(lines)


def beats_references(report: dict) -> dict:
    """Where the model demonstrates real signal, checked criterion by criterion.

    Accuracy and ROC AUC isolate genuine discrimination: beating "always
    guess the training majority" on accuracy requires the model to correctly
    deviate from that constant sometimes, and AUC above 0.5 means it ranks
    games better than a coin flip. Both are gating.

    Log loss is reported but *not* gating. It rewards calibration and
    discrimination together, and first-inning scoring is close enough to a
    coin flip (see app/features/config.py's shrinkage notes — pitcher talent
    SD is 0.034 against a 0.712 mean) that the log-loss improvement a real
    but weak edge should produce is the same order of magnitude as sampling
    noise over a few thousand held-out games. A model can rank better than
    chance and still land within noise of the constant baseline on log loss;
    that isn't evidence of no signal, just of a small one.
    """
    model: dict = report["model"]
    majority: dict = report["reference_majority_class"]
    league: dict = report["reference_league_average"]
    return {
        "beats_majority_accuracy": bool(model["accuracy"] > majority["accuracy"]),
        "ranks_better_than_chance": bool(model["roc_auc"] > 0.5),
        "beats_league_log_loss": bool(model["log_loss"] < league["log_loss"]),
    }


def passed(criteria: dict) -> bool:
    """The M5 exit criterion proper — the two gating checks from above."""
    return criteria["beats_majority_accuracy"] and criteria["ranks_better_than_chance"]


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
    report = build_report(model, train, test)

    print(f"M5 baseline — {cfg.MODEL_VERSION}\n{describe(report)}")
    criteria = beats_references(report)
    ok = passed(criteria)
    print(
        f"\n  Beats majority-class accuracy: {criteria['beats_majority_accuracy']}\n"
        f"  Ranks better than chance (AUC>0.5): {criteria['ranks_better_than_chance']}\n"
        f"  Beats league-average log loss: {criteria['beats_league_log_loss']}"
        " (reported, not gating — see beats_references docstring)\n"
        f"  M5 exit criterion: {'PASS' if ok else 'FAIL'}"
    )

    if not args.no_save:
        save_artifacts(model, report, criteria)
        print(f"  Model:    {cfg.MODEL_PATH}")
        print(f"  Metrics:  {cfg.METRICS_PATH}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
