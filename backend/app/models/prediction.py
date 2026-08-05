"""Prediction and grading tables (M3).

``predictions`` is append-only: one row per (game, model version). Re-running
the same model over the same game updates that row rather than adding a
second one, but a *new* model version writes a new row — which is what makes
the M11 "model accuracy over time" and M6 model-comparison views possible
without rewriting history.

``prediction_results`` is the accountability half: once a game is final, each
prediction is graded against the actual outcome. It's a separate table (not
columns on ``predictions``) so an ungraded prediction is simply a missing
row, rather than a nullable "correct" flag that's ambiguous between "not
graded yet" and "graded, and wrong".
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UtcDateTime
from app.models.game import Game

# JSONB on Postgres; plain JSON elsewhere so the models stay testable on
# SQLite without a live database.
JSONType = JSONB().with_variant(JSON(), "sqlite")

NRFI = "NRFI"
YRFI = "YRFI"
LABELS = (NRFI, YRFI)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "game_pk", "model_version", name="uq_prediction_per_model_version"
        ),
        CheckConstraint(
            "predicted_label IN ('NRFI', 'YRFI')", name="valid_label"
        ),
        CheckConstraint(
            "nrfi_probability >= 0 AND nrfi_probability <= 1",
            name="nrfi_probability_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="confidence_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_pk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.game_pk", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )

    predicted_label: Mapped[str] = mapped_column(String(4), nullable=False)
    nrfi_probability: Mapped[float] = mapped_column(Float, nullable=False)
    yrfi_probability: Mapped[float] = mapped_column(Float, nullable=False)
    # Distance from a coin flip, rescaled to 0-1. Kept as a stored column so
    # the dashboard can sort/filter on it without recomputing (requirements.md).
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Feature snapshot the prediction was made from — this is what makes an
    # old prediction explainable after the feature pipeline has moved on.
    features: Mapped[dict | None] = mapped_column(JSONType)
    explanation: Mapped[str | None] = mapped_column(Text)

    predicted_at: Mapped[dt.datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), nullable=False
    )

    game: Mapped[Game] = relationship(back_populates="predictions")
    result: Mapped["PredictionResult | None"] = relationship(
        back_populates="prediction",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Prediction g={self.game_pk} {self.predicted_label} "
            f"p={self.nrfi_probability:.3f} v={self.model_version}>"
        )


class PredictionResult(Base):
    __tablename__ = "prediction_results"
    __table_args__ = (
        CheckConstraint(
            "actual_label IN ('NRFI', 'YRFI')", name="valid_actual_label"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    game_pk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.game_pk", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actual_label: Mapped[str] = mapped_column(String(4), nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # ROI inputs (requirements.md historical stats). Null when the game had
    # no odds captured — accuracy still works, ROI just excludes it.
    odds_american: Mapped[int | None] = mapped_column(Integer)
    stake: Mapped[float | None] = mapped_column(Numeric(8, 2))
    profit: Mapped[float | None] = mapped_column(Numeric(8, 2))

    graded_at: Mapped[dt.datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), nullable=False
    )

    prediction: Mapped[Prediction] = relationship(back_populates="result")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        outcome = "WIN" if self.correct else "LOSS"
        return f"<PredictionResult g={self.game_pk} {outcome}>"
