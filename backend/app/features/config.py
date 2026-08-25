"""Feature pipeline configuration (M4).

Constants live here rather than being scattered through the computation so
the knobs that shape the model are visible in one place — and so M6 can tune
them without archaeology.
"""

from __future__ import annotations

# --- Shrinkage -------------------------------------------------------------
# A rate observed over n appearances is pulled toward the league average:
#
#     (observed * n + league * k) / (n + k)
#
# k is "how many observations of evidence the league average is worth". At
# n == k the estimate sits halfway between the two.
#
# These are MEASURED, not guessed — see app/features/shrinkage.py, which
# decomposes the observed spread of each statistic into real talent plus
# sampling noise and solves for k. Re-derive with:
#
#     python -m app.features.shrinkage
#
# Fitted on 2018-2022 so the constants don't peek at the seasons M5/M6 hold
# out. The values are large because first-inning splits are mostly noise: a
# pitcher's career first-inning NRFI% has a talent SD of just 0.034 against a
# league mean of 0.712, so most of the spread between pitchers isn't real.
# An earlier hand-picked k=12 made the feature three times more spread out
# than the outcome it predicts.
#
# k is in the units named on each line.
PITCHER_NRFI_K = 182.0    # starts (career/season samples)
# Fit separately from PITCHER_NRFI_K: that constant was measured against
# each pitcher's full career rate, then reused as-is for the 5-start
# "recent form" window below — a borrowed hyperparameter, not a measured
# one. Measuring it directly (app.features.shrinkage.estimate_recent_k)
# gives 169, barely different from the borrowed 182: a pitcher's last 5
# starts genuinely don't carry much more signal than 5-sample binomial
# noise would produce on their own. Kept as its own constant so the value
# is justified by its own fit rather than coincidence.
PITCHER_NRFI_RECENT_K = 169.0  # last-5-start samples
PITCHER_RUNS_K = 160.0    # starts
PITCHER_WHIP_K = 94.0     # starts
PITCHER_K_RATE_K = 86.0   # batters faced  (≈ the known ~70 PA K% stabilization)
PITCHER_BB_RATE_K = 202.0  # batters faced

TEAM_SCORED_K = 388.0     # games
TEAM_RUNS_K = 442.0       # games
TEAM_K_RATE_K = 934.0     # batters

PARK_NRFI_K = 779.0       # games

# --- Recent-form windows ---------------------------------------------------
# Windows count *dates on which the entity appeared*, not calendar days.
# For a starting pitcher that's exactly "last N starts" — nobody starts twice
# in a day. For a team it's "last N game days", which differs from "last N
# games" only on the ~2% of days that are doubleheaders.
PITCHER_FORM_WINDOW = 5   # last 5 starts (requirements.md game-detail view)
TEAM_FORM_WINDOW = 30     # last 30 game days, ~a month of baseball

# --- Cold-start fallbacks --------------------------------------------------
# Used only before *any* prior game exists (opening day 2018, the first row
# in the dataset). After that the league baselines are themselves computed
# as-of, so they carry real information rather than a guess.
FALLBACK_NRFI_RATE = 0.50
FALLBACK_SCORED_1ST_RATE = 0.28  # one team scoring in the 1st, not the game
FALLBACK_RUNS_1ST = 0.50
FALLBACK_K_RATE = 0.22
FALLBACK_BB_RATE = 0.08
FALLBACK_WHIP_1ST = 0.45

# --- Output ----------------------------------------------------------------
IDENTITY_COLUMNS = ["game_pk", "game_date", "season", "home_team_id", "away_team_id"]
TARGET_COLUMN = "nrfi"

# The model-facing columns, in a stable order. M5 trains on exactly this list,
# so anything added here flows through to training without further wiring.
FEATURE_COLUMNS = [
    # Starting pitchers — the dominant signal for a first-inning market.
    "home_sp_nrfi_rate",
    "away_sp_nrfi_rate",
    "home_sp_nrfi_rate_season",
    "away_sp_nrfi_rate_season",
    "home_sp_nrfi_rate_recent",
    "away_sp_nrfi_rate_recent",
    "home_sp_runs_1st_avg",
    "away_sp_runs_1st_avg",
    "home_sp_whip_1st",
    "away_sp_whip_1st",
    "home_sp_k_rate_1st",
    "away_sp_k_rate_1st",
    "home_sp_bb_rate_1st",
    "away_sp_bb_rate_1st",
    "home_sp_starts_prior",
    "away_sp_starts_prior",
    # Team offense in the 1st.
    "home_team_scored_1st_rate",
    "away_team_scored_1st_rate",
    "home_team_scored_1st_rate_season",
    "away_team_scored_1st_rate_season",
    "home_team_scored_1st_rate_recent",
    "away_team_scored_1st_rate_recent",
    "home_team_runs_1st_avg",
    "away_team_runs_1st_avg",
    "home_team_k_rate_1st",
    "away_team_k_rate_1st",
    # Home/away split: the home team's record at home, the away team's on the
    # road. Same feature name, different slice per side.
    "home_team_scored_1st_rate_split",
    "away_team_scored_1st_rate_split",
    "home_team_games_prior",
    "away_team_games_prior",
    # Ballpark.
    "park_nrfi_rate",
    "park_games_prior",
]
