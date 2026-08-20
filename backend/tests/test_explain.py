"""Tests for the M8 rule-based explanation generator."""

from app.models.prediction import Prediction
from app.queries.explain import generate_explanation


def _prediction(features):
    return Prediction(
        game_pk=1,
        model_name="logreg",
        model_version="v1",
        predicted_label="NRFI",
        nrfi_probability=0.6,
        yrfi_probability=0.4,
        confidence=0.2,
        features=features,
    )


def test_no_features_yields_no_explanation():
    assert generate_explanation(_prediction({})) == []
    assert generate_explanation(_prediction(None)) == []


def test_favors_the_stronger_starting_pitcher():
    features = {"home_sp_nrfi_rate": 0.80, "away_sp_nrfi_rate": 0.60}
    explanation = generate_explanation(_prediction(features))

    assert len(explanation) == 1
    assert "Home starter" in explanation[0]
    assert "80%" in explanation[0]
    assert "60%" in explanation[0]


def test_favors_the_away_pitcher_when_away_is_better():
    features = {"home_sp_nrfi_rate": 0.55, "away_sp_nrfi_rate": 0.75}
    explanation = generate_explanation(_prediction(features))

    assert "Away starter" in explanation[0]


def test_lower_whip_is_the_better_pitcher():
    features = {"home_sp_whip_1st": 0.30, "away_sp_whip_1st": 0.55}
    explanation = generate_explanation(_prediction(features))

    assert "Home starter" in explanation[0]
    assert "0.30" in explanation[0]
    assert "0.55" in explanation[0]


def test_higher_team_scoring_rate_is_the_louder_offense():
    features = {"home_team_scored_1st_rate": 0.40, "away_team_scored_1st_rate": 0.20}
    explanation = generate_explanation(_prediction(features))

    assert "Home team" in explanation[0]
    assert "40%" in explanation[0]


def test_park_factor_compares_against_a_coin_flip_not_league_average():
    features = {"park_nrfi_rate": 0.65}
    explanation = generate_explanation(_prediction(features))

    assert len(explanation) == 1
    assert "suppressed" in explanation[0]
    assert "65%" in explanation[0]


def test_park_factor_reads_favors_below_a_coin_flip():
    features = {"park_nrfi_rate": 0.35}
    explanation = generate_explanation(_prediction(features))

    assert "favored" in explanation[0]


def test_a_park_rate_at_exactly_the_coin_flip_is_not_a_factor():
    features = {"park_nrfi_rate": 0.5}
    assert generate_explanation(_prediction(features)) == []


def test_factors_are_ranked_by_magnitude_most_divergent_first():
    features = {
        # Small pitcher gap.
        "home_sp_nrfi_rate": 0.71,
        "away_sp_nrfi_rate": 0.70,
        # Large team-scoring gap — should rank first.
        "home_team_scored_1st_rate": 0.45,
        "away_team_scored_1st_rate": 0.15,
    }
    explanation = generate_explanation(_prediction(features))

    assert explanation[0].startswith("Home team")
    assert explanation[1].startswith(("Home starter", "Away starter"))


def test_respects_top_n():
    features = {
        "home_sp_nrfi_rate": 0.80,
        "away_sp_nrfi_rate": 0.60,
        "home_sp_nrfi_rate_recent": 0.85,
        "away_sp_nrfi_rate_recent": 0.55,
        "home_sp_whip_1st": 0.30,
        "away_sp_whip_1st": 0.60,
        "home_team_scored_1st_rate": 0.45,
        "away_team_scored_1st_rate": 0.15,
        "park_nrfi_rate": 0.65,
    }
    assert len(generate_explanation(_prediction(features), top_n=2)) == 2
    assert len(generate_explanation(_prediction(features), top_n=10)) == 5
