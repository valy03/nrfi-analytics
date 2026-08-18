"""Tests for the M6 XGBoost candidate (app.training.xgboost_model)."""

import numpy as np
import pandas as pd
import pytest

from app.features import config as fcfg
from app.training.xgboost_model import train_xgboost


def _separable_matrix(n_per_season=150, seasons=(2018, 2019, 2020)):
    rng = np.random.default_rng(3)
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


def test_train_xgboost_returns_a_fitted_model_with_sane_predictions():
    train = _separable_matrix()

    model = train_xgboost(train)
    proba = model.predict_proba(train[fcfg.FEATURE_COLUMNS])[:, 1]

    assert proba.shape == (len(train),)
    assert (proba >= 0).all() and (proba <= 1).all()
    # It should have actually picked up the wired feature, not stalled at a
    # single constant prediction for every row.
    assert proba.std() > 0.01


def test_train_xgboost_requires_at_least_two_seasons():
    train = _separable_matrix(seasons=(2018,))

    with pytest.raises(ValueError):
        train_xgboost(train)


def test_train_xgboost_uses_a_bounded_tree_count():
    """Early stopping against the internal validation season should pick a
    tree count well short of the max probe budget on data this simple.
    """
    train = _separable_matrix()

    model = train_xgboost(train)

    assert 0 < model.n_estimators < 1000
