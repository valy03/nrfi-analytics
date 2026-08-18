"""Tests for the M5 baseline model.

Pure logic on synthetic frames, same spirit as test_features.py: no database,
no real feature matrix, so the suite stays fast and offline. The headline
test (``test_baseline_beats_naive_references_on_separable_data``) mirrors the
actual M5 exit criterion — given features that genuinely carry signal, the
trained model must beat both naive references on held-out data.
"""

import numpy as np
import pandas as pd
import pytest

from app.features import config as fcfg
from app.training.baseline import (
    beats_references,
    build_report,
    passed,
    train_baseline,
)
from app.training.evaluate import (
    compute_metrics,
    league_average_reference,
    majority_class_reference,
)
from app.training.split import time_based_split


# --- time_based_split --------------------------------------------------


def _seasoned_frame(seasons):
    return pd.DataFrame({"season": seasons, "value": range(len(seasons))})


def test_split_puts_each_season_on_the_correct_side():
    matrix = _seasoned_frame([2018, 2019, 2022, 2023, 2024, 2025])
    train, test = time_based_split(matrix, cutoff_season=2024)

    assert sorted(train["season"].unique()) == [2018, 2019, 2022, 2023]
    assert sorted(test["season"].unique()) == [2024, 2025]


def test_split_covers_every_row_exactly_once():
    matrix = _seasoned_frame([2018, 2019, 2020, 2024, 2025])
    train, test = time_based_split(matrix, cutoff_season=2024)

    assert len(train) + len(test) == len(matrix)
    assert set(train["value"]).isdisjoint(set(test["value"]))


def test_split_handles_a_cutoff_with_no_test_rows():
    matrix = _seasoned_frame([2018, 2019])
    train, test = time_based_split(matrix, cutoff_season=2024)

    assert len(train) == 2
    assert test.empty


# --- evaluate.compute_metrics -------------------------------------------


def test_compute_metrics_perfect_predictions():
    y_true = [0, 1, 0, 1, 1]
    y_proba = [0.0, 1.0, 0.0, 1.0, 1.0]

    metrics = compute_metrics(y_true, y_proba)

    assert metrics.accuracy == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.roc_auc == 1.0
    assert metrics.log_loss == pytest.approx(0.0, abs=1e-6)


def test_compute_metrics_worst_case_predictions():
    y_true = [0, 1, 0, 1]
    y_proba = [1.0, 0.0, 1.0, 0.0]

    metrics = compute_metrics(y_true, y_proba)

    assert metrics.accuracy == 0.0
    assert metrics.roc_auc == 0.0


def test_compute_metrics_single_class_reports_nan_auc():
    """ROC AUC is undefined with only one class present — must not raise."""
    y_true = [0, 0, 0]
    y_proba = [0.3, 0.4, 0.2]

    metrics = compute_metrics(y_true, y_proba)

    assert np.isnan(metrics.roc_auc)


# --- naive references ----------------------------------------------------


def test_majority_class_reference_picks_the_more_common_label():
    train_target = pd.Series([1, 1, 1, 0])  # 75% NRFI
    prediction = majority_class_reference(train_target, n=5)

    assert (prediction == 1.0).all()
    assert len(prediction) == 5


def test_majority_class_reference_picks_zero_when_yrfi_dominates():
    train_target = pd.Series([0, 0, 0, 1])
    prediction = majority_class_reference(train_target, n=3)

    assert (prediction == 0.0).all()


def test_league_average_reference_is_the_training_rate():
    train_target = pd.Series([1, 1, 0, 0, 1])  # 60% NRFI
    prediction = league_average_reference(train_target, n=4)

    assert prediction == pytest.approx(0.6)
    assert len(prediction) == 4


# --- the exit criterion: model beats naive references ----------------------


def _separable_matrix(n_per_season=200, seasons=(2018, 2019, 2020, 2021, 2024, 2025)):
    """A synthetic matrix where one feature deterministically sets the label.

    Every M4 feature column is populated (constant, uninformative noise) so
    ``train_baseline`` runs the real feature list end to end; only
    ``home_sp_nrfi_rate`` actually carries signal, via a monotone relationship
    with the label plus a little noise, similar to the real (weak) signal a
    single feature carries in production.
    """
    rng = np.random.default_rng(0)
    rows = []
    for season in seasons:
        for i in range(n_per_season):
            # Spans both sides of 0.5 so the Bayes-optimal decision actually
            # varies per row — otherwise "always predict the majority label"
            # *is* the optimal classifier and the model can never out-accuracy
            # it, no matter how much real signal the feature carries.
            signal = rng.uniform(0.25, 0.85)
            label = int(rng.uniform(0, 1) < signal)
            row = {col: 0.5 for col in fcfg.FEATURE_COLUMNS}
            row["home_sp_nrfi_rate"] = signal
            row["season"] = season
            row[fcfg.TARGET_COLUMN] = label
            rows.append(row)
    return pd.DataFrame(rows)


def test_baseline_beats_naive_references_on_separable_data():
    matrix = _separable_matrix()
    train, test = time_based_split(matrix, cutoff_season=2024)

    model = train_baseline(train)
    report = build_report(model, train, test)
    criteria = beats_references(report)

    assert criteria["beats_majority_accuracy"]
    assert criteria["ranks_better_than_chance"]
    assert passed(criteria)
    assert report["model"]["roc_auc"] > 0.5
    assert report["model"]["log_loss"] < report["reference_league_average"]["log_loss"]


def test_passed_gates_on_accuracy_and_auc_but_not_log_loss():
    """A weak-but-real edge can lose to the constant baseline on log loss by
    pure sampling noise (see beats_references's docstring) — that shouldn't
    flip the overall verdict to FAIL.
    """
    report = {
        "model": {"accuracy": 0.52, "roc_auc": 0.51, "log_loss": 0.70},
        "reference_majority_class": {"accuracy": 0.48, "roc_auc": 0.5, "log_loss": 5.0},
        "reference_league_average": {"accuracy": 0.48, "roc_auc": 0.5, "log_loss": 0.69},
    }

    criteria = beats_references(report)

    assert criteria["beats_majority_accuracy"]
    assert criteria["ranks_better_than_chance"]
    assert not criteria["beats_league_log_loss"]
    assert passed(criteria)


def test_report_records_seasons_on_each_side_of_the_split():
    matrix = _separable_matrix(n_per_season=20)
    train, test = time_based_split(matrix, cutoff_season=2024)

    model = train_baseline(train)
    report = build_report(model, train, test)

    assert report["train"]["seasons"] == [2018, 2019, 2020, 2021]
    assert report["test"]["seasons"] == [2024, 2025]
    assert report["train"]["n"] == len(train)
    assert report["test"]["n"] == len(test)
