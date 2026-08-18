"""Tests for the M4 feature pipeline.

The headline test is ``test_features_are_unchanged_by_deleting_the_future``:
build features for a game, then delete every game after it and rebuild. If a
single number moves, the pipeline is reading the future. That one test is
worth more than the rest of this file combined — leakage doesn't raise, it
just makes M5's metrics look wonderful and production look broken.

``compute_features`` is pure pandas, so everything here runs on small
synthetic frames with no database involved.
"""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from app.features import config as cfg
from app.features.compute import compute_features
from app.features.shrinkage import estimate_k

HOME_TEAM, AWAY_TEAM = 111, 147
HOME_SP, AWAY_SP = 1001, 2002


def _game(game_pk, date, nrfi, home=HOME_TEAM, away=AWAY_TEAM,
          home_sp=HOME_SP, away_sp=AWAY_SP):
    return {
        "game_pk": game_pk,
        "game_date": pd.Timestamp(date),
        "season": pd.Timestamp(date).year,
        "home_team_id": home,
        "away_team_id": away,
        "home_sp_id": home_sp,
        "away_sp_id": away_sp,
        "nrfi": nrfi,
    }


def _team_line(game_pk, date, team_id, is_home, runs, k=1, batters=4):
    return {
        "game_pk": game_pk,
        "game_date": pd.Timestamp(date),
        "team_id": team_id,
        "is_home": is_home,
        "runs_1st": runs,
        "strikeouts_1st": k,
        "batters_1st": batters,
    }


def _pitcher_line(game_pk, date, pitcher_id, runs, hits=1, walks=0, k=1, bf=4):
    return {
        "game_pk": game_pk,
        "game_date": pd.Timestamp(date),
        "pitcher_id": pitcher_id,
        "runs_1st": runs,
        "hits_1st": hits,
        "walks_1st": walks,
        "strikeouts_1st": k,
        "batters_faced_1st": bf,
    }


def _season(n_games=40, start="2024-04-01"):
    """A synthetic season: the same two teams and starters, every other day.

    The home starter is excellent (never allows a run in the 1st); the away
    starter is poor (always allows one). That asymmetry is what the
    directional tests below key on.
    """
    games, team_lines, pitcher_lines = [], [], []
    day = dt.date.fromisoformat(start)
    for i in range(n_games):
        date = day + dt.timedelta(days=2 * i)
        game_pk = 900_000 + i
        away_scores = 1  # away team scores off the weak home... no: see below
        # Home starter faces the away lineup and is untouchable; the away
        # starter is hit around, so the home team always scores.
        games.append(_game(game_pk, date, nrfi=False))
        team_lines += [
            _team_line(game_pk, date, HOME_TEAM, True, runs=1),
            _team_line(game_pk, date, AWAY_TEAM, False, runs=0),
        ]
        pitcher_lines += [
            _pitcher_line(game_pk, date, HOME_SP, runs=0),
            _pitcher_line(game_pk, date, AWAY_SP, runs=away_scores),
        ]
    return (
        pd.DataFrame(games),
        pd.DataFrame(team_lines),
        pd.DataFrame(pitcher_lines),
    )


# --- the leakage guarantee -------------------------------------------------


def test_features_are_unchanged_by_deleting_the_future():
    """The test this milestone lives or dies by.

    Features for game N must depend only on games 1..N-1. So computing them
    with the whole season present, and again with everything after game N
    deleted, must give byte-identical numbers.
    """
    games, team_lines, pitcher_lines = _season(n_games=40)
    full = compute_features(games, team_lines, pitcher_lines)

    cutoff_index = 25
    cutoff_pk = games.loc[cutoff_index, "game_pk"]
    cutoff_date = games.loc[cutoff_index, "game_date"]

    past_games = games[games["game_date"] <= cutoff_date]
    past_pks = set(past_games["game_pk"])
    truncated = compute_features(
        past_games,
        team_lines[team_lines["game_pk"].isin(past_pks)],
        pitcher_lines[pitcher_lines["game_pk"].isin(past_pks)],
    )

    row_full = full[full["game_pk"] == cutoff_pk].reset_index(drop=True)
    row_cut = truncated[truncated["game_pk"] == cutoff_pk].reset_index(drop=True)

    pd.testing.assert_frame_equal(
        row_full[cfg.FEATURE_COLUMNS], row_cut[cfg.FEATURE_COLUMNS]
    )


def test_every_game_is_unaffected_by_its_own_result():
    """Flipping a game's own outcome must not change that game's features."""
    games, team_lines, pitcher_lines = _season(n_games=20)
    before = compute_features(games, team_lines, pitcher_lines)

    # Rewrite the last game's result completely.
    last_pk = games["game_pk"].iloc[-1]
    games2 = games.copy()
    games2.loc[games2["game_pk"] == last_pk, "nrfi"] = True
    team_lines2 = team_lines.copy()
    team_lines2.loc[team_lines2["game_pk"] == last_pk, "runs_1st"] = 9
    pitcher_lines2 = pitcher_lines.copy()
    pitcher_lines2.loc[pitcher_lines2["game_pk"] == last_pk, "runs_1st"] = 9

    after = compute_features(games2, team_lines2, pitcher_lines2)

    row_before = before[before["game_pk"] == last_pk].reset_index(drop=True)
    row_after = after[after["game_pk"] == last_pk].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        row_before[cfg.FEATURE_COLUMNS], row_after[cfg.FEATURE_COLUMNS]
    )


def test_doubleheader_second_game_ignores_the_first():
    """Same-date games must not feed each other.

    Game 1 of a doubleheader finishes before game 2 starts, so using it would
    be legal in hindsight — but the prediction job runs in the morning, when
    neither has happened. A strict date cutoff keeps training and inference
    computing the same number.
    """
    games, team_lines, pitcher_lines = _season(n_games=10)
    date = games["game_date"].iloc[-1]

    twin_pk = 999_999
    games = pd.concat(
        [games, pd.DataFrame([_game(twin_pk, date.date(), nrfi=True)])],
        ignore_index=True,
    )
    features = compute_features(games, team_lines, pitcher_lines)

    first = features[features["game_pk"] == games["game_pk"].iloc[-2]]
    second = features[features["game_pk"] == twin_pk]

    for column in cfg.FEATURE_COLUMNS:
        assert first[column].iloc[0] == pytest.approx(second[column].iloc[0]), (
            f"{column} differs between two games on the same date — the "
            "second game is seeing the first"
        )


# --- correctness of the aggregates -----------------------------------------


def test_first_game_has_no_prior_history():
    games, team_lines, pitcher_lines = _season(n_games=5)
    features = compute_features(games, team_lines, pitcher_lines)
    first = features.iloc[0]

    assert first["home_sp_starts_prior"] == 0
    assert first["away_sp_starts_prior"] == 0
    assert first["home_team_games_prior"] == 0
    assert first["park_games_prior"] == 0


def test_prior_counts_increment_by_one_per_game():
    games, team_lines, pitcher_lines = _season(n_games=6)
    features = compute_features(games, team_lines, pitcher_lines)

    assert list(features["home_sp_starts_prior"]) == [0, 1, 2, 3, 4, 5]
    assert list(features["home_team_games_prior"]) == [0, 1, 2, 3, 4, 5]


def test_a_dominant_starter_scores_higher_than_a_poor_one():
    """The home starter never allows a run; the away starter always does."""
    games, team_lines, pitcher_lines = _season(n_games=60)
    features = compute_features(games, team_lines, pitcher_lines)
    last = features.iloc[-1]

    assert last["home_sp_nrfi_rate"] > last["away_sp_nrfi_rate"]
    assert last["home_sp_runs_1st_avg"] < last["away_sp_runs_1st_avg"]


def test_scoring_team_rates_above_shut_out_team():
    games, team_lines, pitcher_lines = _season(n_games=60)
    features = compute_features(games, team_lines, pitcher_lines)
    last = features.iloc[-1]

    # Home team scores in the 1st every game; away team never does.
    assert last["home_team_scored_1st_rate"] > last["away_team_scored_1st_rate"]
    assert last["home_team_runs_1st_avg"] > last["away_team_runs_1st_avg"]


def test_recent_form_window_forgets_old_games():
    """A pitcher who was bad then turned good should look good recently."""
    games, team_lines, pitcher_lines = [], [], []
    day = dt.date(2024, 4, 1)
    # 20 bad starts, then 5 clean ones.
    for i in range(25):
        date = day + dt.timedelta(days=2 * i)
        pk = 800_000 + i
        runs = 2 if i < 20 else 0
        games.append(_game(pk, date, nrfi=(runs == 0)))
        team_lines += [
            _team_line(pk, date, HOME_TEAM, True, runs=0),
            _team_line(pk, date, AWAY_TEAM, False, runs=runs),
        ]
        pitcher_lines += [
            _pitcher_line(pk, date, HOME_SP, runs=runs),
            _pitcher_line(pk, date, AWAY_SP, runs=0),
        ]
    # One more game, to read the features off.
    final_date = day + dt.timedelta(days=2 * 25)
    games.append(_game(870_000, final_date, nrfi=None))

    features = compute_features(
        pd.DataFrame(games), pd.DataFrame(team_lines), pd.DataFrame(pitcher_lines)
    )
    last = features.iloc[-1]

    # The last 5 starts were all clean, the career includes 20 bad ones.
    assert last["home_sp_nrfi_rate_recent"] > last["home_sp_nrfi_rate"]


def test_home_away_split_uses_the_right_slice():
    """Home team's home record, away team's road record — not their overall."""
    games, team_lines, pitcher_lines = [], [], []
    day = dt.date(2024, 4, 1)
    for i in range(40):
        date = day + dt.timedelta(days=2 * i)
        pk = 700_000 + i
        # Alternate which club is at home; a team only scores when at home.
        home, away = (HOME_TEAM, AWAY_TEAM) if i % 2 == 0 else (AWAY_TEAM, HOME_TEAM)
        games.append(_game(pk, date, nrfi=False, home=home, away=away))
        team_lines += [
            _team_line(pk, date, home, True, runs=1),
            _team_line(pk, date, away, False, runs=0),
        ]
        pitcher_lines += [
            _pitcher_line(pk, date, HOME_SP, runs=0),
            _pitcher_line(pk, date, AWAY_SP, runs=1),
        ]

    features = compute_features(
        pd.DataFrame(games), pd.DataFrame(team_lines), pd.DataFrame(pitcher_lines)
    )
    last = features.iloc[-1]

    # Every team scores at home and never on the road, so the home side's
    # split must exceed the away side's.
    assert (
        last["home_team_scored_1st_rate_split"]
        > last["away_team_scored_1st_rate_split"]
    )


# --- cold start ------------------------------------------------------------


def test_debut_pitcher_falls_back_to_the_league_average():
    games, team_lines, pitcher_lines = _season(n_games=30)

    # A brand-new starter appears for the away side in one extra game.
    debut_date = games["game_date"].iloc[-1] + dt.timedelta(days=2)
    games = pd.concat(
        [
            games,
            pd.DataFrame(
                [_game(880_000, debut_date.date(), nrfi=None, away_sp=555_555)]
            ),
        ],
        ignore_index=True,
    )
    features = compute_features(games, team_lines, pitcher_lines)
    debut = features.iloc[-1]

    assert debut["away_sp_starts_prior"] == 0
    # No history, so the estimate is the league average — not 0, not NaN.
    assert 0.4 < debut["away_sp_nrfi_rate"] < 1.0
    assert not np.isnan(debut["away_sp_nrfi_rate"])


def test_unannounced_starter_falls_back_to_the_league_average_instead_of_crashing():
    """A NULL away_sp_id (MLB hasn't confirmed a starter yet) must be handled
    the same way as a debut pitcher, not blow up the as-of join. This is the
    normal state of tomorrow's slate — there are almost always a couple of
    TBD starters — so build_full_matrix computing over the *whole* games
    table (M7's features_for_games) must not choke on one being present
    anywhere in it.
    """
    games, team_lines, pitcher_lines = _season(n_games=30)

    tbd_date = games["game_date"].iloc[-1] + dt.timedelta(days=2)
    row = _game(881_000, tbd_date.date(), nrfi=None)
    row["away_sp_id"] = None
    games = pd.concat([games, pd.DataFrame([row])], ignore_index=True)

    features = compute_features(games, team_lines, pitcher_lines)
    tbd = features.iloc[-1]

    assert tbd["away_sp_starts_prior"] == 0
    assert 0.4 < tbd["away_sp_nrfi_rate"] < 1.0
    assert not features[cfg.FEATURE_COLUMNS].isna().any().any()


def test_no_nans_anywhere_including_the_very_first_game():
    games, team_lines, pitcher_lines = _season(n_games=10)
    features = compute_features(games, team_lines, pitcher_lines)

    assert not features[cfg.FEATURE_COLUMNS].isna().any().any()


def test_shrinkage_pulls_small_samples_toward_the_league():
    """One clean start shouldn't make a pitcher look like prime deGrom."""
    games, team_lines, pitcher_lines = _season(n_games=40)

    # A pitcher with exactly one (perfect) start to his name.
    rookie_date = games["game_date"].iloc[5]
    rookie_pk = 860_000
    games = pd.concat(
        [
            games,
            pd.DataFrame([_game(rookie_pk, rookie_date.date(), nrfi=True,
                                away_sp=777_777)]),
            pd.DataFrame(
                [
                    _game(
                        860_001,
                        (games["game_date"].iloc[-1] + dt.timedelta(days=2)).date(),
                        nrfi=None,
                        away_sp=777_777,
                    )
                ]
            ),
        ],
        ignore_index=True,
    )
    pitcher_lines = pd.concat(
        [
            pitcher_lines,
            pd.DataFrame([_pitcher_line(rookie_pk, rookie_date, 777_777, runs=0)]),
        ],
        ignore_index=True,
    )

    features = compute_features(games, team_lines, pitcher_lines)
    rookie = features.iloc[-1]

    assert rookie["away_sp_starts_prior"] == 1
    # A single flawless start is nowhere near enough to reach 100%.
    assert rookie["away_sp_nrfi_rate"] < 0.80


# --- the inference path ----------------------------------------------------


def test_unplayed_game_gets_features_and_a_null_target():
    """The M7 path: a game with no box score still produces a full row."""
    games, team_lines, pitcher_lines = _season(n_games=20)
    future_date = games["game_date"].iloc[-1] + dt.timedelta(days=2)
    games = pd.concat(
        [games, pd.DataFrame([_game(890_000, future_date.date(), nrfi=None)])],
        ignore_index=True,
    )

    features = compute_features(games, team_lines, pitcher_lines)
    future = features[features["game_pk"] == 890_000].iloc[0]

    assert pd.isna(future[cfg.TARGET_COLUMN])
    assert not future[cfg.FEATURE_COLUMNS].isna().any()
    # It has the full history of the 20 played games behind it.
    assert future["home_sp_starts_prior"] == 20


def test_training_and_inference_agree_on_the_same_game():
    """A game's features must not change once its result is known.

    Computed twice — once while it's still unplayed, once after it's been
    played and labeled — the feature row must be identical. This is the
    train/serve symmetry the whole design exists to guarantee.
    """
    games, team_lines, pitcher_lines = _season(n_games=20)
    target_date = games["game_date"].iloc[-1] + dt.timedelta(days=2)
    target_pk = 895_000

    # Before: scheduled, no result, no box score.
    pending = pd.concat(
        [games, pd.DataFrame([_game(target_pk, target_date.date(), nrfi=None)])],
        ignore_index=True,
    )
    at_inference = compute_features(pending, team_lines, pitcher_lines)

    # After: the game happened and got labeled.
    played = pending.copy()
    played.loc[played["game_pk"] == target_pk, "nrfi"] = False
    team_lines_after = pd.concat(
        [
            team_lines,
            pd.DataFrame(
                [
                    _team_line(target_pk, target_date, HOME_TEAM, True, runs=3),
                    _team_line(target_pk, target_date, AWAY_TEAM, False, runs=0),
                ]
            ),
        ],
        ignore_index=True,
    )
    pitcher_lines_after = pd.concat(
        [
            pitcher_lines,
            pd.DataFrame(
                [
                    _pitcher_line(target_pk, target_date, HOME_SP, runs=0),
                    _pitcher_line(target_pk, target_date, AWAY_SP, runs=3),
                ]
            ),
        ],
        ignore_index=True,
    )
    at_training = compute_features(played, team_lines_after, pitcher_lines_after)

    before = at_inference[at_inference["game_pk"] == target_pk].reset_index(drop=True)
    after = at_training[at_training["game_pk"] == target_pk].reset_index(drop=True)

    pd.testing.assert_frame_equal(
        before[cfg.FEATURE_COLUMNS], after[cfg.FEATURE_COLUMNS]
    )


def test_output_shape_is_the_declared_contract():
    games, team_lines, pitcher_lines = _season(n_games=5)
    features = compute_features(games, team_lines, pitcher_lines)

    expected = cfg.IDENTITY_COLUMNS + cfg.FEATURE_COLUMNS + [cfg.TARGET_COLUMN]
    assert list(features.columns) == expected
    assert len(features) == 5


# --- the shrinkage estimator ----------------------------------------------


def test_estimate_k_is_large_when_talent_barely_varies():
    """All entities identical -> observed spread is pure noise -> huge k."""
    rng = np.random.default_rng(0)
    n = np.full(200, 100.0)
    observed = rng.binomial(100, 0.7, size=200) / 100.0

    estimate = estimate_k(observed, n, "identical talent")

    assert estimate.talent_sd < 0.02
    assert estimate.k > 300


def test_estimate_k_is_small_when_talent_varies_widely():
    """Genuinely different entities -> real spread -> trust the observation."""
    rng = np.random.default_rng(0)
    talent = rng.uniform(0.3, 0.9, size=200)
    n = np.full(200, 100.0)
    observed = rng.binomial(100, talent) / 100.0

    estimate = estimate_k(observed, n, "varied talent")

    assert estimate.talent_sd > 0.10
    assert estimate.k < 30
