"""Estimating how much to shrink (M4).

Shrinking a rate toward the league average needs a constant k — "how many
observations of evidence the league average is worth". Guessing it is the
usual approach and it's usually wrong: the first pass at this pipeline used
k=12 for pitchers, which produced a feature spanning 0.61-0.80 while the
outcome it predicts spanned only 0.69-0.76. The feature was three times more
spread out than reality, because a career first-inning record is mostly
noise and was being taken at face value.

The fix is to measure it. For an entity observed n times, the variance of its
observed rate decomposes as::

    Var(observed) = Var(talent) + E[unit_variance / n]
                    \\_________/   \\__________________/
                     real spread     sampling noise

Everything except Var(talent) is measurable, so::

    Var(talent) = Var(observed) - E[unit_variance / n]
    k           = unit_variance / Var(talent)

which is the classic empirical-Bayes shrinkage constant. Intuitively: k is
large when talent barely varies (so an observation says little) and small
when it varies a lot (so an observation says a lot).

A useful check that this works: run against first-inning strikeout rate and
it returns k ≈ 86 batters faced, independently reproducing the ~70 PA
"stabilization point" for K% that the sabermetric literature arrived at by
other means.

Constants are estimated over 2018-2022 only — the likely M5 training window —
so a hyperparameter baked into the features doesn't peek at the held-out
seasons.

Run it to re-derive the values in config.py:
    python -m app.features.shrinkage
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import session_scope

# Seasons the constants are fitted on. Deliberately excludes the later years
# so M5/M6 can hold them out honestly.
FIT_SEASONS = (2018, 2022)

# Entities with fewer observations than this are too noisy to inform the fit.
MIN_OBSERVATIONS = 20


@dataclass(frozen=True)
class ShrinkageEstimate:
    name: str
    league_mean: float
    talent_sd: float
    k: float
    entities: int

    def __str__(self) -> str:
        return (
            f"{self.name:24s} mean={self.league_mean:.4f}  "
            f"talent_sd={self.talent_sd:.4f}  k={self.k:7.0f}  "
            f"(n={self.entities})"
        )


def estimate_k(
    observed: np.ndarray,
    counts: np.ndarray,
    name: str,
    unit_variance: float | None = None,
) -> ShrinkageEstimate:
    """Empirical-Bayes shrinkage constant for a set of per-entity rates.

    ``observed`` is each entity's observed rate, ``counts`` how many
    observations it came from. ``unit_variance`` is the variance of a single
    observation; for a 0/1 rate it defaults to the binomial ``p(1-p)``.
    """
    observed = np.asarray(observed, dtype=float)
    counts = np.asarray(counts, dtype=float)

    mean = float(np.average(observed, weights=counts))
    if unit_variance is None:
        unit_variance = mean * (1.0 - mean)

    var_observed = float(np.average((observed - mean) ** 2, weights=counts))
    sampling_noise = float(np.average(unit_variance / counts, weights=counts))
    var_talent = max(var_observed - sampling_noise, 1e-9)

    return ShrinkageEstimate(
        name=name,
        league_mean=mean,
        talent_sd=float(np.sqrt(var_talent)),
        k=float(unit_variance / var_talent),
        entities=len(observed),
    )


_PITCHER_SQL = """
    SELECT s.pitcher_id,
           count(*)                                            AS starts,
           sum(s.batters_faced_1st)                            AS batters,
           avg(CASE WHEN s.runs_1st = 0 THEN 1.0 ELSE 0 END)   AS nrfi_rate,
           sum(s.strikeouts_1st)::float / NULLIF(sum(s.batters_faced_1st),0) AS k_rate,
           sum(s.walks_1st)::float / NULLIF(sum(s.batters_faced_1st),0)      AS bb_rate,
           avg(s.runs_1st)                                     AS runs_avg,
           avg(s.hits_1st + s.walks_1st)                       AS whip,
           var_samp(s.runs_1st)                                AS runs_var,
           var_samp(s.hits_1st + s.walks_1st)                  AS whip_var
      FROM pitcher_game_stats s
      JOIN games g ON g.game_pk = s.game_pk
     WHERE s.is_starter AND g.season BETWEEN :lo AND :hi
     GROUP BY 1
    HAVING count(*) >= :min_obs
"""

_TEAM_SQL = """
    SELECT s.team_id,
           count(*)                                            AS games,
           sum(s.batters_1st)                                  AS batters,
           avg(CASE WHEN s.runs_1st > 0 THEN 1.0 ELSE 0 END)   AS scored_rate,
           sum(s.strikeouts_1st)::float / NULLIF(sum(s.batters_1st),0) AS k_rate,
           avg(s.runs_1st)                                     AS runs_avg,
           var_samp(s.runs_1st)                                AS runs_var
      FROM team_game_stats s
      JOIN games g ON g.game_pk = s.game_pk
     WHERE g.season BETWEEN :lo AND :hi
     GROUP BY 1
"""

_PARK_SQL = """
    SELECT home_team_id,
           count(*)                                     AS games,
           avg(CASE WHEN nrfi THEN 1.0 ELSE 0 END)      AS nrfi_rate
      FROM games
     WHERE season BETWEEN :lo AND :hi AND nrfi IS NOT NULL
     GROUP BY 1
"""


def estimate_all(
    session: Session, seasons: tuple[int, int] = FIT_SEASONS
) -> list[ShrinkageEstimate]:
    """Re-derive every shrinkage constant the pipeline uses."""
    params = {"lo": seasons[0], "hi": seasons[1], "min_obs": MIN_OBSERVATIONS}
    connection = session.connection()
    pitchers = pd.read_sql(text(_PITCHER_SQL), connection, params=params)
    teams = pd.read_sql(text(_TEAM_SQL), connection, params=params)
    parks = pd.read_sql(
        text(_PARK_SQL), connection, params={"lo": seasons[0], "hi": seasons[1]}
    )

    return [
        estimate_k(pitchers.nrfi_rate, pitchers.starts, "pitcher NRFI% (starts)"),
        estimate_k(pitchers.k_rate, pitchers.batters, "pitcher K% (batters)"),
        estimate_k(pitchers.bb_rate, pitchers.batters, "pitcher BB% (batters)"),
        # Counts, not rates: a single start's variance is measured directly
        # rather than assumed binomial.
        estimate_k(
            pitchers.runs_avg,
            pitchers.starts,
            "pitcher runs/start",
            unit_variance=float(pitchers.runs_var.mean()),
        ),
        estimate_k(
            pitchers.whip,
            pitchers.starts,
            "pitcher WHIP/start",
            unit_variance=float(pitchers.whip_var.mean()),
        ),
        estimate_k(teams.scored_rate, teams.games, "team scored-1st% (games)"),
        estimate_k(teams.k_rate, teams.batters, "team K% (batters)"),
        estimate_k(
            teams.runs_avg,
            teams.games,
            "team runs/game",
            unit_variance=float(teams.runs_var.mean()),
        ),
        estimate_k(parks.nrfi_rate, parks.games, "park NRFI% (games)"),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-derive the shrinkage constants used by the features."
    )
    parser.add_argument("--start-season", type=int, default=FIT_SEASONS[0])
    parser.add_argument("--end-season", type=int, default=FIT_SEASONS[1])
    args = parser.parse_args(argv)

    with session_scope() as session:
        estimates = estimate_all(
            session, (args.start_season, args.end_season)
        )

    print(
        f"Shrinkage constants fitted on {args.start_season}-{args.end_season}:\n"
    )
    for estimate in estimates:
        print(f"  {estimate}")
    print(
        "\nk is in the units of the count column shown in parentheses. "
        "Copy into app/features/config.py."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
