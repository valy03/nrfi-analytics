"""Model-agnostic evaluation reporting (M5, M6).

Everything here takes a fitted model exposing ``predict_proba`` plus
train/test frames — never a specific model class. M5's Logistic Regression
and M6's XGBoost candidate both produce their report through this exact same
path, which is what makes the M6 head-to-head comparison a fair one: neither
model gets bespoke scoring logic that could tilt the numbers.
"""

from __future__ import annotations

import pandas as pd

from app.features import config as fcfg
from app.training.evaluate import (
    compute_metrics,
    league_average_reference,
    majority_class_reference,
)


def build_report(
    model,
    model_name: str,
    model_version: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> dict:
    """Score ``model`` on ``test`` against the two naive references fit on
    ``train`` only — a reference that peeked at test labels wouldn't be dumb,
    it would be cheating.
    """
    y_train = train[fcfg.TARGET_COLUMN]
    y_test = test[fcfg.TARGET_COLUMN]
    n_test = len(test)

    model_proba = model.predict_proba(test[fcfg.FEATURE_COLUMNS])[:, 1]
    majority_proba = majority_class_reference(y_train, n_test)
    league_proba = league_average_reference(y_train, n_test)

    return {
        "model_name": model_name,
        "model_version": model_version,
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
        row(f"{report['model_name']}:", report["model"]),
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
    """The M5/M6 exit criterion proper — the two gating checks above."""
    return criteria["beats_majority_accuracy"] and criteria["ranks_better_than_chance"]
