"""As-of feature computation (M4) — pure pandas, no database.

Everything here answers one question: *what could we have known before this
game started?* Get that wrong and the model looks brilliant in M5 and useless
in production, so the rule is enforced structurally rather than by care.

The leakage rule
----------------
Every aggregate is computed over games played on a **strictly earlier date**
than the game it describes. Not "all games this season" (that includes the
future), and not "shift by one row" (on a doubleheader that leaks game 1 into
game 2's features — legitimate at training time, but unavailable at 9am when
the prediction job actually runs). A strict date cutoff produces the same
number whether you compute it in hindsight or on the morning of the game,
which is the only property that makes training and inference comparable.

Mechanically: build a running total through each date an entity appeared,
then look it up with a backward ``merge_asof`` and
``allow_exact_matches=False``. The as-of join is what enforces "strictly
before", and — unlike an exact index lookup — it answers for *any* date, not
just ones the entity played on. That distinction is the whole ballgame: an
exact lookup works perfectly for a game already in the books and returns
nothing for tomorrow's, which is how a pipeline ends up scoring brilliantly
in training and predicting from empty history in production.

Cold starts
-----------
A pitcher making his debut has no prior starts, so his observed rate is
undefined rather than zero. Every rate is therefore shrunk toward the league
average::

    (observed * n + league * k) / (n + k)

At n = 0 the estimate *is* the league average; it earns its way toward the
observed rate as evidence accumulates. The league average is itself computed
as-of, for the same reason as everything else — a constant fitted over all
seasons would quietly leak the future into 2018.

The sample sizes (``*_starts_prior``, ``*_games_prior``) are exposed as
features too, so the model can learn how much to trust a shrunk estimate
rather than being told.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.features import config as cfg

# Per-appearance values accumulated for each entity.
PITCHER_VALUES = [
    "nrfi_start",
    "runs_1st",
    "hits_1st",
    "walks_1st",
    "strikeouts_1st",
    "batters_faced_1st",
]
TEAM_VALUES = ["scored_1st", "runs_1st", "strikeouts_1st", "batters_1st"]

_COUNT = "_n"


# --------------------------------------------------------------------------
# as-of primitives
# --------------------------------------------------------------------------


def _running_totals(
    frame: pd.DataFrame,
    entity_cols: list[str],
    value_cols: list[str],
    window: int | None = None,
) -> pd.DataFrame:
    """Per-entity totals *through* each date the entity appeared, inclusive.

    ``window`` limits the sum to the entity's last N *appearance dates*. For
    a starting pitcher that is exactly "last N starts" — nobody starts twice
    in a day. For a team it is "last N game days", which differs from "last N
    games" only on the ~2% of days that are doubleheaders.

    The result is a lookup table, not the feature: the "strictly before"
    cutoff is applied at query time by :func:`_as_of`.
    """
    columns = value_cols + [_COUNT]
    grouped = frame.groupby(entity_cols + ["game_date"], sort=True)
    grid = grouped[value_cols].sum()
    grid[_COUNT] = grouped.size()
    grid = grid.sort_index().reset_index()

    if window is None:
        totals = grid.groupby(entity_cols, sort=False)[columns].cumsum()
    else:
        totals = (
            grid.groupby(entity_cols, sort=False)[columns]
            .rolling(window, min_periods=1)
            .sum()
            # groupby().rolling() prepends the group keys to the index; grid
            # has a plain RangeIndex underneath, so drop them and restore it.
            .droplevel(list(range(len(entity_cols))))
            .sort_index()
        )

    out = pd.concat([grid[entity_cols + ["game_date"]], totals], axis=1)
    # merge_asof requires the right-hand side sorted by the join key.
    return out.sort_values("game_date").reset_index(drop=True)


def _as_of(
    totals: pd.DataFrame,
    keys: pd.DataFrame,
    entity_cols: list[str],
    value_cols: list[str],
) -> pd.DataFrame:
    """Look up each row's totals as of the day *before* its date.

    This is where the leakage rule is enforced, and it is deliberately a
    backward as-of join rather than an exact index lookup. An exact lookup
    only answers for dates the entity actually appeared on — fine for a
    played game, useless for tomorrow's, which is precisely the asymmetry
    that makes a pipeline score brilliantly in training and fail in
    production. ``allow_exact_matches=False`` is the "strictly before" cutoff:
    same-day games, including both ends of a doubleheader, never see each
    other.

    Entities with no prior appearances come back as zeros, which the callers
    turn into the league average via shrinkage. A missing entity key — an
    unannounced starting pitcher, stored as NULL until MLB confirms one — is
    treated exactly the same way: remapped to a sentinel that can't match any
    real id, so it comes back with zero prior appearances (and the same
    league-average fallback a debut pitcher gets) instead of crashing the
    dtype cast merge_asof needs. Real MLB ids are always positive, so -1 never
    collides with a legitimate pitcher, team, or park.
    """
    columns = value_cols + [_COUNT]
    left = keys.sort_values("game_date")
    # merge_asof refuses to join keys of differing dtype (int32 vs int64 is
    # enough), and `.dt.year` hands back int32 on some platforms.
    for col in entity_cols:
        left[col] = (
            pd.to_numeric(left[col], errors="coerce")
            .fillna(-1)
            .astype(totals[col].dtype)
        )
    merged = pd.merge_asof(
        left,
        totals,
        on="game_date",
        by=entity_cols,
        direction="backward",
        allow_exact_matches=False,
    )
    merged.index = left.index
    return merged.sort_index()[columns].fillna(0.0)


def _league_totals(frame: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    """League-wide running totals by date — the shrinkage target.

    As-of for the same reason everything else is: a league average fitted
    over all seasons would leak 2025 into 2018.
    """
    grouped = frame.groupby("game_date", sort=True)
    grid = grouped[value_cols].sum()
    grid[_COUNT] = grouped.size()
    return grid.sort_index().cumsum().reset_index()


def _shrink(
    numerator: pd.Series,
    denominator: pd.Series,
    league_rate: pd.Series,
    k: float,
) -> pd.Series:
    """Blend an observed rate toward the league average by sample size."""
    denominator = denominator.fillna(0.0)
    return (numerator.fillna(0.0) + league_rate * k) / (denominator + k)


def _rate(
    numerator: pd.Series, denominator: pd.Series, fallback: float
) -> pd.Series:
    """A plain rate, falling back where there's no evidence at all."""
    with np.errstate(divide="ignore", invalid="ignore"):
        out = numerator / denominator.replace(0, np.nan)
    return out.fillna(fallback)


# --------------------------------------------------------------------------
# input preparation
# --------------------------------------------------------------------------


def _prepare_pitcher_lines(pitcher_lines: pd.DataFrame) -> pd.DataFrame:
    lines = pitcher_lines.copy()
    lines["game_date"] = pd.to_datetime(lines["game_date"])
    lines["season"] = lines["game_date"].dt.year
    # A "clean" first inning for the pitcher: no runs allowed.
    lines["nrfi_start"] = (lines["runs_1st"] == 0).astype(float)
    for col in PITCHER_VALUES:
        lines[col] = pd.to_numeric(lines[col], errors="coerce").fillna(0.0)
    return lines


def _prepare_team_lines(team_lines: pd.DataFrame) -> pd.DataFrame:
    lines = team_lines.copy()
    lines["game_date"] = pd.to_datetime(lines["game_date"])
    lines["season"] = lines["game_date"].dt.year
    lines["scored_1st"] = (lines["runs_1st"] > 0).astype(float)
    for col in TEAM_VALUES:
        lines[col] = pd.to_numeric(lines[col], errors="coerce").fillna(0.0)
    return lines


def _prepare_games(games: pd.DataFrame) -> pd.DataFrame:
    out = games.copy()
    out["game_date"] = pd.to_datetime(out["game_date"])
    if "season" not in out.columns:
        out["season"] = out["game_date"].dt.year
    out["nrfi"] = pd.to_numeric(out["nrfi"], errors="coerce")
    return out.sort_values(["game_date", "game_pk"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# feature assembly
# --------------------------------------------------------------------------


def _league_as_of(
    games: pd.DataFrame, totals: pd.DataFrame, value_cols: list[str]
) -> pd.DataFrame:
    """League totals as of the day before each game — same cutoff, no entity."""
    left = games[["game_date"]].sort_values("game_date")
    merged = pd.merge_asof(
        left,
        totals,
        on="game_date",
        direction="backward",
        allow_exact_matches=False,
    )
    merged.index = left.index
    return merged.sort_index()[value_cols + [_COUNT]].fillna(0.0)


def _league_rates(
    games: pd.DataFrame,
    pitcher_lines: pd.DataFrame,
    team_lines: pd.DataFrame,
    labeled: pd.DataFrame,
) -> pd.DataFrame:
    """As-of league baselines, one row per game."""
    sp = _league_as_of(
        games, _league_totals(pitcher_lines, PITCHER_VALUES), PITCHER_VALUES
    )
    tm = _league_as_of(
        games, _league_totals(team_lines, TEAM_VALUES), TEAM_VALUES
    )
    pk = _league_as_of(games, _league_totals(labeled, ["nrfi"]), ["nrfi"])

    return pd.DataFrame(
        {
            "sp_nrfi": _rate(
                sp["nrfi_start"], sp[_COUNT], cfg.FALLBACK_NRFI_RATE
            ),
            "sp_runs": _rate(
                sp["runs_1st"], sp[_COUNT], cfg.FALLBACK_RUNS_1ST
            ),
            "sp_whip": _rate(
                sp["hits_1st"] + sp["walks_1st"],
                sp[_COUNT],
                cfg.FALLBACK_WHIP_1ST,
            ),
            "sp_k": _rate(
                sp["strikeouts_1st"],
                sp["batters_faced_1st"],
                cfg.FALLBACK_K_RATE,
            ),
            "sp_bb": _rate(
                sp["walks_1st"], sp["batters_faced_1st"], cfg.FALLBACK_BB_RATE
            ),
            "team_scored": _rate(
                tm["scored_1st"], tm[_COUNT], cfg.FALLBACK_SCORED_1ST_RATE
            ),
            "team_runs": _rate(
                tm["runs_1st"], tm[_COUNT], cfg.FALLBACK_RUNS_1ST
            ),
            "team_k": _rate(
                tm["strikeouts_1st"], tm["batters_1st"], cfg.FALLBACK_K_RATE
            ),
            "park_nrfi": _rate(
                pk["nrfi"], pk[_COUNT], cfg.FALLBACK_NRFI_RATE
            ),
        }
    )


def _pitcher_features(
    games: pd.DataFrame,
    pitcher_lines: pd.DataFrame,
    league: pd.DataFrame,
    out: pd.DataFrame,
) -> None:
    career = _running_totals(pitcher_lines, ["pitcher_id"], PITCHER_VALUES)
    season = _running_totals(
        pitcher_lines, ["pitcher_id", "season"], PITCHER_VALUES
    )
    recent = _running_totals(
        pitcher_lines,
        ["pitcher_id"],
        PITCHER_VALUES,
        window=cfg.PITCHER_FORM_WINDOW,
    )

    for side in ("home", "away"):
        sp_id = games[f"{side}_sp_id"]
        by_career = _as_of(
            career,
            pd.DataFrame({"pitcher_id": sp_id, "game_date": games["game_date"]}),
            ["pitcher_id"],
            PITCHER_VALUES,
        )
        by_season = _as_of(
            season,
            pd.DataFrame(
                {
                    "pitcher_id": sp_id,
                    "season": games["season"],
                    "game_date": games["game_date"],
                }
            ),
            ["pitcher_id", "season"],
            PITCHER_VALUES,
        )
        by_recent = _as_of(
            recent,
            pd.DataFrame({"pitcher_id": sp_id, "game_date": games["game_date"]}),
            ["pitcher_id"],
            PITCHER_VALUES,
        )

        n = by_career[_COUNT]
        out[f"{side}_sp_starts_prior"] = n
        out[f"{side}_sp_nrfi_rate"] = _shrink(
            by_career["nrfi_start"], n, league["sp_nrfi"], cfg.PITCHER_NRFI_K
        )
        out[f"{side}_sp_nrfi_rate_season"] = _shrink(
            by_season["nrfi_start"],
            by_season[_COUNT],
            league["sp_nrfi"],
            cfg.PITCHER_NRFI_K,
        )
        out[f"{side}_sp_nrfi_rate_recent"] = _shrink(
            by_recent["nrfi_start"],
            by_recent[_COUNT],
            league["sp_nrfi"],
            cfg.PITCHER_NRFI_RECENT_K,
        )
        out[f"{side}_sp_runs_1st_avg"] = _shrink(
            by_career["runs_1st"], n, league["sp_runs"], cfg.PITCHER_RUNS_K
        )
        out[f"{side}_sp_whip_1st"] = _shrink(
            by_career["hits_1st"] + by_career["walks_1st"],
            n,
            league["sp_whip"],
            cfg.PITCHER_WHIP_K,
        )
        out[f"{side}_sp_k_rate_1st"] = _shrink(
            by_career["strikeouts_1st"],
            by_career["batters_faced_1st"],
            league["sp_k"],
            cfg.PITCHER_K_RATE_K,
        )
        out[f"{side}_sp_bb_rate_1st"] = _shrink(
            by_career["walks_1st"],
            by_career["batters_faced_1st"],
            league["sp_bb"],
            cfg.PITCHER_BB_RATE_K,
        )


def _team_features(
    games: pd.DataFrame,
    team_lines: pd.DataFrame,
    league: pd.DataFrame,
    out: pd.DataFrame,
) -> None:
    career = _running_totals(team_lines, ["team_id"], TEAM_VALUES)
    season = _running_totals(team_lines, ["team_id", "season"], TEAM_VALUES)
    recent = _running_totals(
        team_lines, ["team_id"], TEAM_VALUES, window=cfg.TEAM_FORM_WINDOW
    )
    split = _running_totals(team_lines, ["team_id", "is_home"], TEAM_VALUES)

    for side in ("home", "away"):
        team_id = games[f"{side}_team_id"]
        is_home = side == "home"
        by_career = _as_of(
            career,
            pd.DataFrame({"team_id": team_id, "game_date": games["game_date"]}),
            ["team_id"],
            TEAM_VALUES,
        )
        by_season = _as_of(
            season,
            pd.DataFrame(
                {
                    "team_id": team_id,
                    "season": games["season"],
                    "game_date": games["game_date"],
                }
            ),
            ["team_id", "season"],
            TEAM_VALUES,
        )
        by_recent = _as_of(
            recent,
            pd.DataFrame({"team_id": team_id, "game_date": games["game_date"]}),
            ["team_id"],
            TEAM_VALUES,
        )
        # The home team's record at home; the away team's on the road.
        by_split = _as_of(
            split,
            pd.DataFrame(
                {
                    "team_id": team_id,
                    "is_home": is_home,
                    "game_date": games["game_date"],
                }
            ),
            ["team_id", "is_home"],
            TEAM_VALUES,
        )

        n = by_career[_COUNT]
        out[f"{side}_team_games_prior"] = n
        out[f"{side}_team_scored_1st_rate"] = _shrink(
            by_career["scored_1st"], n, league["team_scored"], cfg.TEAM_SCORED_K
        )
        out[f"{side}_team_scored_1st_rate_season"] = _shrink(
            by_season["scored_1st"],
            by_season[_COUNT],
            league["team_scored"],
            cfg.TEAM_SCORED_K,
        )
        out[f"{side}_team_scored_1st_rate_recent"] = _shrink(
            by_recent["scored_1st"],
            by_recent[_COUNT],
            league["team_scored"],
            cfg.TEAM_SCORED_K,
        )
        out[f"{side}_team_scored_1st_rate_split"] = _shrink(
            by_split["scored_1st"],
            by_split[_COUNT],
            league["team_scored"],
            cfg.TEAM_SCORED_K,
        )
        out[f"{side}_team_runs_1st_avg"] = _shrink(
            by_career["runs_1st"], n, league["team_runs"], cfg.TEAM_RUNS_K
        )
        out[f"{side}_team_k_rate_1st"] = _shrink(
            by_career["strikeouts_1st"],
            by_career["batters_1st"],
            league["team_k"],
            cfg.TEAM_K_RATE_K,
        )


def _park_features(
    games: pd.DataFrame,
    labeled: pd.DataFrame,
    league: pd.DataFrame,
    out: pd.DataFrame,
) -> None:
    """Ballpark effect, keyed on the home team (one club, one park)."""
    park = _running_totals(labeled, ["home_team_id"], ["nrfi"])
    by_park = _as_of(
        park,
        pd.DataFrame(
            {
                "home_team_id": games["home_team_id"],
                "game_date": games["game_date"],
            }
        ),
        ["home_team_id"],
        ["nrfi"],
    )
    out["park_games_prior"] = by_park[_COUNT]
    out["park_nrfi_rate"] = _shrink(
        by_park["nrfi"], by_park[_COUNT], league["park_nrfi"], cfg.PARK_NRFI_K
    )


def compute_features(
    games: pd.DataFrame,
    team_lines: pd.DataFrame,
    pitcher_lines: pd.DataFrame,
) -> pd.DataFrame:
    """Build the feature matrix for every game in ``games``.

    ``games`` needs ``game_pk``, ``game_date``, ``home_team_id``,
    ``away_team_id``, ``home_sp_id``, ``away_sp_id`` and (where known)
    ``nrfi``. Unplayed games are welcome — they simply have no box-score rows
    to contribute, and come back with features but a null target. That's the
    inference path, and it runs through exactly this function.

    ``team_lines`` and ``pitcher_lines`` are the observed per-game first
    innings; only *starters* should appear in ``pitcher_lines``.
    """
    games = _prepare_games(games)
    team_lines = _prepare_team_lines(team_lines)
    pitcher_lines = _prepare_pitcher_lines(pitcher_lines)

    # Park history can only be built from games whose outcome is known.
    labeled = games[games["nrfi"].notna()][
        ["game_pk", "game_date", "home_team_id", "nrfi"]
    ]

    league = _league_rates(games, pitcher_lines, team_lines, labeled)

    out = games[
        ["game_pk", "game_date", "season", "home_team_id", "away_team_id"]
    ].copy()
    _pitcher_features(games, pitcher_lines, league, out)
    _team_features(games, team_lines, league, out)
    _park_features(games, labeled, league, out)
    out[cfg.TARGET_COLUMN] = games["nrfi"]

    return out[cfg.IDENTITY_COLUMNS + cfg.FEATURE_COLUMNS + [cfg.TARGET_COLUMN]]
