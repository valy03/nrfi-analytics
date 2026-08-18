"""Response schemas for the historical-results endpoints (M8)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class PredictionHistoryItem(BaseModel):
    game_pk: int
    game_date: dt.date
    home_team: str  # abbreviation
    away_team: str
    predicted_label: str
    actual_label: str | None
    correct: bool | None
    confidence: float
    nrfi_probability: float
    model_name: str
    model_version: str


class AccuracyBucket(BaseModel):
    period: str  # "overall", a year ("2026"), or a month ("2026-08")
    total: int
    correct: int
    accuracy: float | None
    # Identical to `accuracy` for a binary market bet straight on the
    # predicted side every time — requirements.md names them separately, so
    # both are exposed, but there's no second computation happening here.
    win_rate: float | None
    # No odds source yet (M8 fast-follow) — ROI isn't computable.
    roi: float | None = None


class AccuracyReport(BaseModel):
    overall: AccuracyBucket
    monthly: list[AccuracyBucket]
    yearly: list[AccuracyBucket]
