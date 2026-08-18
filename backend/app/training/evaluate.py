"""Evaluation metrics and naive reference baselines (M5).

A model's own metrics don't say much in isolation — 65% accuracy sounds
good until you learn the league-wide NRFI rate is 65%. So every model is
graded against two "dumb" references, each built from the *training* set
only (a reference that peeked at test labels wouldn't be dumb, it would be
cheating):

- ``majority_class_reference`` — predict whichever label was more common in
  training, every time. The floor an accuracy number has to clear.
- ``league_average_reference`` — predict the training NRFI rate as the
  probability for every game. Same accuracy as the majority-class reference
  (it rounds to the same label), but a calibration floor for log loss: a
  model with worse log loss than "just guess the league average" isn't
  learning anything about the specific game.

Neither reference varies its prediction per game, so both have a degenerate
(flat) ROC curve — ``roc_auc`` on a reference is not a meaningful number and
is reported at 0.5 by construction, not because the reference is "50%
accurate at ranking."
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass
class Metrics:
    n: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    log_loss: float

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(y_true, y_proba, threshold: float = 0.5) -> Metrics:
    """Score predicted NRFI probabilities against actual outcomes."""
    y_true = np.asarray(y_true, dtype=int)
    y_proba = np.clip(np.asarray(y_proba, dtype=float), 1e-15, 1 - 1e-15)
    y_pred = (y_proba >= threshold).astype(int)

    has_both_classes = len(np.unique(y_true)) > 1
    return Metrics(
        n=len(y_true),
        accuracy=accuracy_score(y_true, y_pred),
        precision=precision_score(y_true, y_pred, zero_division=0),
        recall=recall_score(y_true, y_pred, zero_division=0),
        f1=f1_score(y_true, y_pred, zero_division=0),
        roc_auc=roc_auc_score(y_true, y_proba) if has_both_classes else float("nan"),
        log_loss=log_loss(y_true, y_proba, labels=[0, 1]),
    )


def majority_class_reference(train_target: pd.Series, n: int) -> np.ndarray:
    """Predict training's more-common label, as a probability, for every row."""
    majority_label = float(train_target.mean() >= 0.5)
    return np.full(n, majority_label)


def league_average_reference(train_target: pd.Series, n: int) -> np.ndarray:
    """Predict training's overall NRFI rate, unchanged, for every row."""
    return np.full(n, float(train_target.mean()))
