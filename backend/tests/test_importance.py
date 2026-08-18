"""Tests for M6 feature importance extraction.

Both extractors are checked the same way: fit a model where exactly one
feature is wired to the label and every other column is pure noise, then
confirm that feature comes out on top. This is the "which stats are
predictive?" question M6 exists to answer, exercised on a case where the
answer is known in advance.
"""

import numpy as np
import pandas as pd

from app.features import config as fcfg
from app.training.baseline import train_baseline
from app.training.importance import (
    logistic_regression_importance,
    xgboost_importance,
)
from app.training.xgboost_model import train_xgboost


def _toy_frame(n_per_season=250, seasons=(2018, 2019)):
    rng = np.random.default_rng(1)
    rows = []
    for season in seasons:
        for _ in range(n_per_season):
            row = {col: rng.uniform(0.3, 0.7) for col in fcfg.FEATURE_COLUMNS}
            signal = rng.uniform(0.2, 0.9)
            row["home_sp_nrfi_rate"] = signal
            row["season"] = season
            row[fcfg.TARGET_COLUMN] = int(rng.uniform(0, 1) < signal)
            rows.append(row)
    return pd.DataFrame(rows)


def test_logistic_regression_importance_ranks_the_wired_feature_highest():
    train = _toy_frame()
    model = train_baseline(train)

    importance = logistic_regression_importance(model)

    assert set(importance.index) == set(fcfg.FEATURE_COLUMNS)
    assert importance.index[0] == "home_sp_nrfi_rate"
    # A real signal should stand well clear of pure noise, not just edge it out.
    assert importance.iloc[0] > importance.iloc[1] * 2


def test_xgboost_importance_ranks_the_wired_feature_highest():
    train = _toy_frame()
    model = train_xgboost(train)

    importance = xgboost_importance(model)

    assert set(importance.index) == set(fcfg.FEATURE_COLUMNS)
    assert importance.index[0] == "home_sp_nrfi_rate"
