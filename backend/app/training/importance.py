"""Feature importance extraction (M6).

Different model families expose "importance" in different units — a
Logistic Regression's scaled coefficient magnitude isn't the same thing as
a tree ensemble's gain-based split importance, and presenting them on one
absolute scale would overstate how comparable they are. What both agree on,
and what M6's "which stats are predictive?" question actually needs, is
*rank*: which features each model leans on most.
"""

from __future__ import annotations

import pandas as pd

from app.features import config as fcfg


def logistic_regression_importance(model) -> pd.Series:
    """Abs(scaled coefficient) — comparable across features because every
    input already passed through the same StandardScaler, so a feature's
    coefficient reflects its effect per standard deviation of itself, not
    per raw unit.
    """
    coefs = model.named_steps["logreg"].coef_[0]
    return (
        pd.Series(abs(coefs), index=fcfg.FEATURE_COLUMNS)
        .sort_values(ascending=False)
    )


def xgboost_importance(model) -> pd.Series:
    """Gain-based importance — the average improvement in the split
    criterion a feature contributes, which is what ``feature_importances_``
    reports for this xgboost version's sklearn API.
    """
    return (
        pd.Series(model.feature_importances_, index=fcfg.FEATURE_COLUMNS)
        .sort_values(ascending=False)
    )
