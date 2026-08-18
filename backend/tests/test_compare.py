"""Tests for M6 head-to-head comparison and champion selection.

``select_champion`` is tested against fabricated report/criteria dicts —
it's pure selection logic and doesn't need a real fitted model to exercise.
``build_candidates`` gets one small end-to-end check on synthetic data to
confirm the two model families actually go through the same split and the
same scoring path.
"""

import numpy as np
import pandas as pd

from app.features import config as fcfg
from app.training import config as cfg
from app.training.compare import build_candidates, select_champion
from app.training.split import time_based_split


def _fake_candidate(model_name, model_version, roc_auc, passes=True):
    return {
        "model": None,
        "report": {
            "model_name": model_name,
            "model_version": model_version,
            "model": {
                "accuracy": 0.55 if passes else 0.40,
                "roc_auc": roc_auc,
                "log_loss": 0.68,
            },
        },
        "criteria": {
            "beats_majority_accuracy": passes,
            "ranks_better_than_chance": roc_auc > 0.5,
            "beats_league_log_loss": passes,
        },
        "importance": pd.Series([0.5, 0.5], index=["a", "b"]),
    }


def test_select_champion_picks_higher_auc_among_passing_candidates():
    a = _fake_candidate("logreg", "v1", roc_auc=0.52)
    b = _fake_candidate("xgboost", "v1", roc_auc=0.58)

    selection = select_champion([a, b])

    assert selection["winner_model_name"] == "xgboost"
    assert "xgboost" in selection["rationale"]
    assert "logreg" in selection["rationale"]


def test_select_champion_prefers_a_passing_candidate_over_a_higher_auc_failure():
    """A candidate that ranks well by chance but fails the gating criteria
    (worse accuracy than the majority-class reference, say) shouldn't win
    just because its raw AUC is higher.
    """
    high_auc_failure = _fake_candidate("suspicious", "v1", roc_auc=0.60, passes=False)
    solid = _fake_candidate("solid", "v1", roc_auc=0.52, passes=True)

    selection = select_champion([high_auc_failure, solid])

    assert selection["winner_model_name"] == "solid"


def test_select_champion_falls_back_to_the_full_field_if_nothing_passes():
    a = _fake_candidate("logreg", "v1", roc_auc=0.49, passes=False)
    b = _fake_candidate("xgboost", "v1", roc_auc=0.47, passes=False)

    selection = select_champion([a, b])

    assert selection["winner_model_name"] == "logreg"
    assert "Neither candidate passed" in selection["rationale"]


def _separable_matrix(n_per_season=150, seasons=(2018, 2019, 2020, 2021, 2024, 2025)):
    rng = np.random.default_rng(2)
    rows = []
    for season in seasons:
        for _ in range(n_per_season):
            signal = rng.uniform(0.25, 0.85)
            label = int(rng.uniform(0, 1) < signal)
            row = {col: 0.5 for col in fcfg.FEATURE_COLUMNS}
            row["home_sp_nrfi_rate"] = signal
            row["season"] = season
            row[fcfg.TARGET_COLUMN] = label
            rows.append(row)
    return pd.DataFrame(rows)


def test_build_candidates_scores_both_models_on_the_same_split():
    matrix = _separable_matrix()
    train, test = time_based_split(matrix, cutoff_season=2024)

    candidates = build_candidates(train, test)

    assert len(candidates) == 2
    names = {c["report"]["model_name"] for c in candidates}
    assert names == {cfg.MODEL_NAME, cfg.XGB_MODEL_NAME}
    for c in candidates:
        assert c["report"]["test"]["n"] == len(test)
        assert c["report"]["train"]["n"] == len(train)
        assert set(c["importance"].index) == set(fcfg.FEATURE_COLUMNS)

    selection = select_champion(candidates)
    versions = {c["report"]["model_version"] for c in candidates}
    assert selection["winner_model_version"] in versions
