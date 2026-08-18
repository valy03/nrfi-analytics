"""Analytics endpoints (M8): frequency chart and leaderboards."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.queries import analytics as analytics_queries
from app.schemas.analytics import (
    ModelPerformanceEntry,
    NrfiFrequencyPoint,
    PitcherLeaderboardEntry,
    TeamLeaderboardEntry,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/nrfi-frequency", response_model=list[NrfiFrequencyPoint])
def get_nrfi_frequency(db: Session = Depends(get_db)) -> list[NrfiFrequencyPoint]:
    return analytics_queries.nrfi_frequency(db)


@router.get("/pitchers", response_model=list[PitcherLeaderboardEntry])
def get_pitcher_leaderboard(
    min_starts: int = Query(10, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[PitcherLeaderboardEntry]:
    return analytics_queries.pitcher_leaderboard(db, min_starts=min_starts, limit=limit)


@router.get("/teams", response_model=list[TeamLeaderboardEntry])
def get_team_leaderboard(
    min_games: int = Query(10, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[TeamLeaderboardEntry]:
    return analytics_queries.team_leaderboard(db, min_games=min_games, limit=limit)


@router.get("/models", response_model=list[ModelPerformanceEntry])
def get_model_performance(db: Session = Depends(get_db)) -> list[ModelPerformanceEntry]:
    return analytics_queries.model_performance(db)
