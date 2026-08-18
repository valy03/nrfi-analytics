"""Games endpoints (M8): today's slate and single-game detail."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.collection.mlb_stats import mlb_today
from app.db.session import get_db
from app.queries import games as games_queries
from app.schemas.games import GameDetail, GameSummary

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=list[GameSummary])
def list_games(
    date: dt.date | None = Query(None, description="Defaults to today (US Eastern)."),
    prediction: Literal["NRFI", "YRFI"] | None = Query(None),
    min_confidence: float | None = Query(None, ge=0, le=1),
    team: str | None = Query(None, description="Search by team name or abbreviation."),
    sort_by: Literal["confidence"] | None = Query(None),
    db: Session = Depends(get_db),
) -> list[GameSummary]:
    target = date or mlb_today()
    return games_queries.games_for_date(
        db,
        target,
        prediction=prediction,
        min_confidence=min_confidence,
        team=team,
        sort_by=sort_by,
    )


@router.get("/{game_pk}", response_model=GameDetail)
def get_game(game_pk: int, db: Session = Depends(get_db)) -> GameDetail:
    detail = games_queries.game_detail(db, game_pk)
    if detail is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return detail
