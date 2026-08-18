"""Response schemas for the analytics endpoints (M8)."""

from __future__ import annotations

from pydantic import BaseModel


class NrfiFrequencyPoint(BaseModel):
    period: str  # a season ("2024") or "overall"
    games: int
    nrfi_rate: float


class PitcherLeaderboardEntry(BaseModel):
    pitcher_id: int
    full_name: str
    starts: int
    nrfi_rate: float
    runs_1st_avg: float


class TeamLeaderboardEntry(BaseModel):
    team_id: int
    abbreviation: str
    games: int
    scored_1st_rate: float


class ModelPerformanceEntry(BaseModel):
    model_name: str
    model_version: str
    total: int
    correct: int
    accuracy: float
