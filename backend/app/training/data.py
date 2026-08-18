"""Shared matrix loading for training scripts (M5, M6)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.db.session import session_scope
from app.features.pipeline import DEFAULT_MATRIX_PATH, build_training_matrix


def load_matrix(path: Path = DEFAULT_MATRIX_PATH) -> pd.DataFrame:
    """The M4 matrix — reuse the cached parquet if present, else rebuild it."""
    if path.exists():
        return pd.read_parquet(path)
    with session_scope() as session:
        return build_training_matrix(session)
