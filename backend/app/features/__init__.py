"""Feature engineering (M4).

``compute`` holds the as-of aggregation — pure pandas, no database, so the
leakage rules are testable in isolation. ``pipeline`` wires it to Postgres
and serves both the training matrix and single-game inference from the same
call; import it directly (``from app.features.pipeline import ...``) rather
than re-exporting it here, so ``python -m app.features.pipeline`` doesn't
import the module twice.
"""

from app.features.compute import compute_features
from app.features.config import FEATURE_COLUMNS, IDENTITY_COLUMNS, TARGET_COLUMN

__all__ = [
    "FEATURE_COLUMNS",
    "IDENTITY_COLUMNS",
    "TARGET_COLUMN",
    "compute_features",
]
