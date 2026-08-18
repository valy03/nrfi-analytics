"""Time-based train/test split (M5).

A random split would mix eras together: the model could train on a 2025
game and be evaluated on a 2019 game, which is not the situation it will
ever actually face in production. It only ever predicts games that haven't
been played yet. Holding out the most recent season(s) as the test set is
the only split that measures the thing M7 will actually do — generalize
forward to games and rosters the model has never seen — rather than measure
how well it memorizes the mix of eras it was shown.

This is a different concern from the leakage the M4 as-of joins already rule
out. Every feature is already computed from strictly-earlier data no matter
how the matrix is sliced afterward, so a random split wouldn't leak future
*information* into a training row. It would still give an optimistic read on
*generalization*, because the model would have already seen rows from the
same season, teams, and rosters as the games it's scored on.
"""

from __future__ import annotations

import pandas as pd

from app.training import config as cfg


def time_based_split(
    matrix: pd.DataFrame, cutoff_season: int = cfg.TEST_SEASON_CUTOFF
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Everything before ``cutoff_season`` trains; everything from it on tests."""
    train = matrix[matrix["season"] < cutoff_season].reset_index(drop=True)
    test = matrix[matrix["season"] >= cutoff_season].reset_index(drop=True)
    return train, test
