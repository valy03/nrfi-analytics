"""ORM models (M3).

Importing this package registers every table on ``Base.metadata`` — which is
what Alembic autogenerate and ``create_all`` both rely on. Import models from
here (``from app.models import Game``) rather than from the submodules, so
the registry is always fully populated.
"""

from app.db.base import Base
from app.models.game import Game
from app.models.game_stats import PitcherGameStats, TeamGameStats
from app.models.pitcher import Pitcher
from app.models.prediction import Prediction, PredictionResult
from app.models.team import Team
from app.models.venue import Venue

__all__ = [
    "Base",
    "Game",
    "Pitcher",
    "PitcherGameStats",
    "Prediction",
    "PredictionResult",
    "Team",
    "TeamGameStats",
    "Venue",
]
