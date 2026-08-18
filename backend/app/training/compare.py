"""M6 — head-to-head comparison and champion selection.

Trains the M5 Logistic Regression and the M6 XGBoost candidate on the exact
same time-based split, scores both through app.training.report (so neither
gets bespoke evaluation logic), and picks a champion with a written reason —
not "XGBoost is fancier". The champion is the one artifact M7 will actually
load for daily inference, saved under a model-agnostic name
(config.CHAMPION_PATH) so the inference path doesn't need to know which
model family is currently in production.

Run it:
    python -m app.training.compare
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from app.features.pipeline import DEFAULT_MATRIX_PATH
from app.training import config as cfg
from app.training.baseline import train_baseline
from app.training.data import load_matrix
from app.training.importance import (
    logistic_regression_importance,
    xgboost_importance,
)
from app.training.report import beats_references, build_report, describe, passed
from app.training.split import time_based_split
from app.training.xgboost_model import train_xgboost


def _importance_dict(series: pd.Series, top_n: int = 10) -> dict:
    """Top-N feature importances as plain floats — numpy scalars (float32
    from xgboost in particular) aren't JSON-serializable as-is.
    """
    return {k: float(v) for k, v in series.head(top_n).items()}


def build_candidates(train: pd.DataFrame, test: pd.DataFrame) -> list[dict]:
    logreg = train_baseline(train)
    logreg_report = build_report(logreg, cfg.MODEL_NAME, cfg.MODEL_VERSION, train, test)

    xgboost_model = train_xgboost(train)
    xgb_report = build_report(
        xgboost_model, cfg.XGB_MODEL_NAME, cfg.XGB_MODEL_VERSION, train, test
    )

    return [
        {
            "model": logreg,
            "report": logreg_report,
            "criteria": beats_references(logreg_report),
            "importance": logistic_regression_importance(logreg),
        },
        {
            "model": xgboost_model,
            "report": xgb_report,
            "criteria": beats_references(xgb_report),
            "importance": xgboost_importance(xgboost_model),
        },
    ]


def select_champion(candidates: list[dict]) -> dict:
    """Pick by held-out ROC AUC among whichever candidates pass the M5/M6
    gating criteria (falling back to the full field if none pass, so there's
    always a documented pick instead of a crash), and write down why.
    """
    passing = [c for c in candidates if passed(c["criteria"])]
    pool = passing if passing else candidates
    winner = max(pool, key=lambda c: c["report"]["model"]["roc_auc"])
    others = [c for c in candidates if c is not winner]

    lines = [
        f"Selected {winner['report']['model_name']} "
        f"({winner['report']['model_version']})."
    ]
    if not passing:
        lines.append(
            "Neither candidate passed the naive-reference gate "
            "(app.training.report.beats_references); picked the higher-AUC "
            "one anyway rather than ship nothing."
        )
    for other in others:
        w_auc = winner["report"]["model"]["roc_auc"]
        o_auc = other["report"]["model"]["roc_auc"]
        lines.append(
            f"Beats {other['report']['model_name']} by {w_auc - o_auc:+.4f} "
            f"AUC on the held-out set ({w_auc:.4f} vs {o_auc:.4f})."
        )

    return {
        "winner_model_name": winner["report"]["model_name"],
        "winner_model_version": winner["report"]["model_version"],
        "rationale": " ".join(lines),
    }


def describe_importance(candidates: list[dict], top_n: int = 8) -> str:
    lines = []
    for c in candidates:
        lines.append(f"  {c['report']['model_name']} — top {top_n} features:")
        for name, value in c["importance"].head(top_n).items():
            lines.append(f"    {name:<40} {value:.4f}")
    return "\n".join(lines)


def save_artifacts(candidates: list[dict], selection: dict) -> None:
    cfg.MODEL_DIR.mkdir(parents=True, exist_ok=True)

    champion = next(
        c
        for c in candidates
        if c["report"]["model_version"] == selection["winner_model_version"]
    )
    joblib.dump(champion["model"], cfg.CHAMPION_PATH)
    cfg.CHAMPION_METRICS_PATH.write_text(
        json.dumps(
            {**champion["report"], "criteria": champion["criteria"], "selection": selection},
            indent=2,
        )
    )

    comparison = {
        "selection": selection,
        "candidates": [
            {
                **c["report"],
                "criteria": c["criteria"],
                "feature_importance": _importance_dict(c["importance"]),
            }
            for c in candidates
        ],
    }
    cfg.COMPARISON_PATH.write_text(json.dumps(comparison, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M6 head-to-head: Logistic Regression vs. XGBoost."
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

    candidates = build_candidates(train, test)

    print("M6 head-to-head\n")
    for c in candidates:
        print(describe(c["report"]))
        print()

    print("Feature importance (top 8 per model):")
    print(describe_importance(candidates))

    selection = select_champion(candidates)
    print(f"\n{selection['rationale']}")

    if not args.no_save:
        save_artifacts(candidates, selection)
        print(f"\n  Champion:   {cfg.CHAMPION_PATH}")
        print(f"  Metrics:    {cfg.CHAMPION_METRICS_PATH}")
        print(f"  Comparison: {cfg.COMPARISON_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
