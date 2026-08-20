"""Rule-based prediction explanations (M8).

Not SHAP — that's a stretch goal (docs/planning.md). Instead: a handful of
comparisons a person would actually reason through (which starter's been
cleaner in the first, which offense has been louder, does this park
suppress first-inning runs), ranked by how much they diverge and rendered
as plain sentences. Every number comes straight from the prediction's
stored feature snapshot — nothing is recomputed, so the explanation always
matches the probability it's explaining, even after the feature pipeline
moves on.

Pitcher and team factors are framed head-to-head (home vs away) rather than
against a hardcoded "league average": every feature is already shrunk
toward whatever the *as-of* league rate was on the day of the game (M4),
and that baseline moves game to game — there's no single constant to
compare against without re-guessing a number M4 went to real effort to stop
guessing (see app/features/config.py). A head-to-head comparison needs no
external reference at all. The one exception is park effect, which has no
natural opponent to compare against, so it's measured against a plainly-
labeled 50% coin flip rather than a claimed league average.

Factor magnitudes are compared directly across features to rank them, which
only works because every feature here already lives on a similar small
scale (rates in/near [0, 1], WHIP in a comparable range) — a genuinely
calibrated importance ranking is what SHAP is for.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.prediction import Prediction

_COIN_FLIP = 0.5


@dataclass
class _Factor:
    magnitude: float
    text: str


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _pitcher_rate_factor(features: dict, key: str, label: str) -> _Factor | None:
    """Higher is better for a rate stat like NRFI% — pick the stronger side."""
    home = features.get(f"home_sp_{key}")
    away = features.get(f"away_sp_{key}")
    if home is None or away is None or home == away:
        return None
    side, better, worse = ("Home", home, away) if home > away else ("Away", away, home)
    return _Factor(
        magnitude=abs(home - away),
        text=(
            f"{side} starter's {label} ({_pct(better)}) is notably stronger "
            f"than the opposing starter's ({_pct(worse)})"
        ),
    )


def _pitcher_whip_factor(features: dict) -> _Factor | None:
    """Lower is better for WHIP — fewer first-inning baserunners allowed."""
    home = features.get("home_sp_whip_1st")
    away = features.get("away_sp_whip_1st")
    if home is None or away is None or home == away:
        return None
    side, better, worse = ("Home", home, away) if home < away else ("Away", away, home)
    return _Factor(
        magnitude=abs(home - away),
        text=(
            f"{side} starter allows fewer first-inning baserunners "
            f"(WHIP {better:.2f} vs {worse:.2f})"
        ),
    )


def _team_scoring_factor(features: dict) -> _Factor | None:
    """Higher first-inning scoring rate pushes toward YRFI, not NRFI."""
    home = features.get("home_team_scored_1st_rate")
    away = features.get("away_team_scored_1st_rate")
    if home is None or away is None or home == away:
        return None
    side, louder, quieter = ("Home", home, away) if home > away else ("Away", away, home)
    quiet_side = "away" if side == "Home" else "home"
    return _Factor(
        magnitude=abs(home - away),
        text=(
            f"{side} team has scored in the 1st ({_pct(louder)} of games) far "
            f"more often than the {quiet_side} side has ({_pct(quieter)})"
        ),
    )


def _park_factor(features: dict) -> _Factor | None:
    park_rate = features.get("park_nrfi_rate")
    if park_rate is None or park_rate == _COIN_FLIP:
        return None
    direction = "suppressed" if park_rate > _COIN_FLIP else "favored"
    return _Factor(
        magnitude=abs(park_rate - _COIN_FLIP),
        text=(
            f"This ballpark has historically {direction} first-inning "
            f"scoring ({_pct(park_rate)} NRFI rate)"
        ),
    )


_PITCHER_RATE_FACTORS = [
    ("nrfi_rate", "career first-inning NRFI rate"),
    ("nrfi_rate_recent", "recent (last-5-start) NRFI rate"),
]


def generate_explanation(prediction: Prediction, top_n: int = 3) -> list[str]:
    """The top ``top_n`` contributing factors, most-divergent first."""
    features = prediction.features or {}
    candidates: list[_Factor] = []

    for key, label in _PITCHER_RATE_FACTORS:
        factor = _pitcher_rate_factor(features, key, label)
        if factor is not None:
            candidates.append(factor)

    for factor in (
        _pitcher_whip_factor(features),
        _team_scoring_factor(features),
        _park_factor(features),
    ):
        if factor is not None:
            candidates.append(factor)

    candidates.sort(key=lambda f: f.magnitude, reverse=True)
    return [f.text for f in candidates[:top_n]]
