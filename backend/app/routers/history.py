"""Historical-results endpoints (M8): past predictions and accuracy."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.queries import history as history_queries
from app.schemas.history import AccuracyBucket, AccuracyReport, PredictionHistoryItem

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/predictions", response_model=list[PredictionHistoryItem])
def list_prediction_history(
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    team: str | None = Query(None, description="Search by team name or abbreviation."),
    model_version: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[PredictionHistoryItem]:
    return history_queries.prediction_history(
        db,
        start_date=start_date,
        end_date=end_date,
        team=team,
        model_version=model_version,
        limit=limit,
        offset=offset,
    )


@router.get("/accuracy", response_model=AccuracyReport)
def get_accuracy(
    model_version: str | None = None, db: Session = Depends(get_db)
) -> AccuracyReport:
    return history_queries.accuracy_report(db, model_version=model_version)


@router.get("/top-picks-accuracy", response_model=AccuracyBucket)
def get_top_picks_accuracy(
    top_n: int = Query(3, ge=1, le=10),
    model_version: str | None = None,
    db: Session = Depends(get_db),
) -> AccuracyBucket:
    return history_queries.top_picks_accuracy(db, top_n=top_n, model_version=model_version)
