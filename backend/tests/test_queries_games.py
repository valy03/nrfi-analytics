"""Tests for the M8 games queries (app.queries.games).

Real ORM rows against the in-memory SQLite ``session`` fixture.
``champion_identity`` is stubbed at the point games.py imports it — same
pattern test_ingestion.py uses for the MLB API — so these don't depend on a
real joblib artifact existing on disk.
"""

import datetime as dt

import pytest

from app.models import Game, Pitcher, PitcherGameStats, Prediction, Team
from app.prediction.infer import ChampionNotFoundError
from app.queries import games as games_queries

HOME_TEAM, AWAY_TEAM = 111, 147
HOME_SP, AWAY_SP = 201, 202
GAME_DATE = dt.date(2026, 8, 18)


@pytest.fixture
def champion(monkeypatch):
    monkeypatch.setattr(games_queries, "champion_identity", lambda: ("logreg", "m5-v1"))


def _teams_and_pitchers(session):
    session.add_all(
        [
            Team(id=HOME_TEAM, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=AWAY_TEAM, name="New York Yankees", abbreviation="NYY"),
            Pitcher(id=HOME_SP, full_name="Home Starter", throws="R"),
            Pitcher(id=AWAY_SP, full_name="Away Starter", throws="L"),
        ]
    )
    session.flush()


def _game(session, game_pk=1, date=GAME_DATE, status="Scheduled", **kwargs):
    game = Game(
        game_pk=game_pk,
        game_date=date,
        season=date.year,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status=status,
        home_probable_pitcher_id=HOME_SP,
        away_probable_pitcher_id=AWAY_SP,
        **kwargs,
    )
    session.add(game)
    session.flush()
    return game


_FEATURES = {
    "home_sp_nrfi_rate": 0.75,
    "away_sp_nrfi_rate": 0.65,
    "home_sp_nrfi_rate_season": 0.74,
    "away_sp_nrfi_rate_season": 0.64,
    "home_sp_nrfi_rate_recent": 0.80,
    "away_sp_nrfi_rate_recent": 0.60,
    "home_sp_whip_1st": 0.35,
    "away_sp_whip_1st": 0.50,
    "home_sp_k_rate_1st": 0.25,
    "away_sp_k_rate_1st": 0.20,
    "home_sp_bb_rate_1st": 0.07,
    "away_sp_bb_rate_1st": 0.09,
    "home_sp_starts_prior": 12,
    "away_sp_starts_prior": 10,
    "home_team_scored_1st_rate": 0.30,
    "away_team_scored_1st_rate": 0.25,
    "home_team_scored_1st_rate_season": 0.31,
    "away_team_scored_1st_rate_season": 0.26,
    "home_team_scored_1st_rate_recent": 0.29,
    "away_team_scored_1st_rate_recent": 0.24,
    "home_team_scored_1st_rate_split": 0.32,
    "away_team_scored_1st_rate_split": 0.23,
    "home_team_runs_1st_avg": 0.35,
    "away_team_runs_1st_avg": 0.28,
    "home_team_k_rate_1st": 0.22,
    "away_team_k_rate_1st": 0.21,
    "home_team_games_prior": 40,
    "away_team_games_prior": 41,
    "park_nrfi_rate": 0.55,
    "park_games_prior": 100,
}


def _prediction(game_pk, model_version="m5-v1", label="NRFI", confidence=0.3, features=None):
    p = 0.5 + confidence / 2 if label == "NRFI" else 0.5 - confidence / 2
    return Prediction(
        game_pk=game_pk,
        model_name="logreg",
        model_version=model_version,
        predicted_label=label,
        nrfi_probability=p,
        yrfi_probability=1 - p,
        confidence=confidence,
        features=features if features is not None else dict(_FEATURES),
    )


# --- games_for_date --------------------------------------------------------


def test_games_for_date_includes_prediction_and_pitcher_rates(session, champion):
    _teams_and_pitchers(session)
    game = _game(session)
    session.add(_prediction(game.game_pk))
    session.flush()

    rows = games_queries.games_for_date(session, GAME_DATE)

    assert len(rows) == 1
    row = rows[0]
    assert row.home_team.abbreviation == "BOS"
    assert row.away_team.abbreviation == "NYY"
    assert row.prediction.predicted_label == "NRFI"
    assert row.home_pitcher.nrfi_rate_career == pytest.approx(0.75)
    assert row.away_pitcher.nrfi_rate_career == pytest.approx(0.65)


def test_games_for_date_prediction_is_none_without_a_champion_match(session, monkeypatch):
    monkeypatch.setattr(
        games_queries, "champion_identity", lambda: (_ for _ in ()).throw(
            ChampionNotFoundError("no champion yet")
        )
    )
    _teams_and_pitchers(session)
    _game(session)

    rows = games_queries.games_for_date(session, GAME_DATE)

    assert rows[0].prediction is None
    assert rows[0].home_pitcher.nrfi_rate_career is None


def test_games_for_date_ignores_a_prediction_from_an_old_model_version(session, champion):
    _teams_and_pitchers(session)
    game = _game(session)
    session.add(_prediction(game.game_pk, model_version="m4-old"))
    session.flush()

    rows = games_queries.games_for_date(session, GAME_DATE)

    assert rows[0].prediction is None


def test_games_for_date_returns_empty_for_a_date_with_no_games(session):
    assert games_queries.games_for_date(session, GAME_DATE) == []


def test_games_for_date_filters_by_prediction_label(session, champion):
    _teams_and_pitchers(session)
    nrfi_game = _game(session, game_pk=1)
    yrfi_game = Game(
        game_pk=2,
        game_date=GAME_DATE,
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Scheduled",
        home_probable_pitcher_id=HOME_SP,
        away_probable_pitcher_id=AWAY_SP,
    )
    session.add(yrfi_game)
    session.flush()
    session.add_all(
        [
            _prediction(nrfi_game.game_pk, label="NRFI"),
            _prediction(yrfi_game.game_pk, label="YRFI"),
        ]
    )
    session.flush()

    rows = games_queries.games_for_date(session, GAME_DATE, prediction="YRFI")

    assert len(rows) == 1
    assert rows[0].game_pk == yrfi_game.game_pk


def test_games_for_date_filters_by_min_confidence(session, champion):
    _teams_and_pitchers(session)
    game = _game(session)
    session.add(_prediction(game.game_pk, confidence=0.1))
    session.flush()

    assert games_queries.games_for_date(session, GAME_DATE, min_confidence=0.5) == []
    assert len(games_queries.games_for_date(session, GAME_DATE, min_confidence=0.05)) == 1


def test_games_for_date_filters_by_team_search(session, champion):
    _teams_and_pitchers(session)
    _game(session)

    assert len(games_queries.games_for_date(session, GAME_DATE, team="bos")) == 1
    assert len(games_queries.games_for_date(session, GAME_DATE, team="nyy")) == 1
    assert games_queries.games_for_date(session, GAME_DATE, team="LAD") == []


def test_games_for_date_sorts_by_confidence_with_unpredicted_last(session, champion):
    _teams_and_pitchers(session)
    low = _game(session, game_pk=1)
    high = Game(
        game_pk=2,
        game_date=GAME_DATE,
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Scheduled",
        home_probable_pitcher_id=HOME_SP,
        away_probable_pitcher_id=AWAY_SP,
    )
    unpredicted = Game(
        game_pk=3,
        game_date=GAME_DATE,
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Scheduled",
    )
    session.add_all([high, unpredicted])
    session.flush()
    session.add_all(
        [
            _prediction(low.game_pk, confidence=0.1),
            _prediction(high.game_pk, confidence=0.4),
        ]
    )
    session.flush()

    rows = games_queries.games_for_date(session, GAME_DATE, sort_by="confidence")

    assert [r.game_pk for r in rows] == [high.game_pk, low.game_pk, unpredicted.game_pk]


# --- game_detail -------------------------------------------------------


def test_game_detail_returns_none_for_an_unknown_game(session):
    assert games_queries.game_detail(session, 999) is None


def test_game_detail_includes_team_stats_and_explanation(session, champion):
    _teams_and_pitchers(session)
    game = _game(session)
    session.add(_prediction(game.game_pk))
    session.flush()

    detail = games_queries.game_detail(session, game.game_pk)

    assert detail is not None
    assert detail.home_team_stats.scored_1st_rate == pytest.approx(0.30)
    assert detail.away_team_stats.scored_1st_rate == pytest.approx(0.25)
    assert len(detail.explanation) > 0
    assert detail.actual_result is None  # not played yet


def test_game_detail_actual_result_present_once_labeled(session, champion):
    _teams_and_pitchers(session)
    game = _game(
        session,
        status="Final",
        home_runs_1st=1,
        away_runs_1st=0,
        first_inning_runs=1,
        nrfi=False,
        home_score=4,
        away_score=2,
    )
    session.add(_prediction(game.game_pk))
    session.flush()

    detail = games_queries.game_detail(session, game.game_pk)

    assert detail.actual_result is not None
    assert detail.actual_result.nrfi is False
    assert detail.actual_result.home_score == 4


def test_game_detail_recent_starts_only_include_strictly_earlier_games(session, champion):
    _teams_and_pitchers(session)
    game = _game(session)
    session.add(_prediction(game.game_pk))

    # An earlier start for the home starter, against the away team.
    earlier = Game(
        game_pk=50,
        game_date=GAME_DATE - dt.timedelta(days=5),
        season=2026,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Final",
        nrfi=True,
    )
    session.add(earlier)
    session.flush()
    session.add(
        PitcherGameStats(
            game_pk=earlier.game_pk,
            pitcher_id=HOME_SP,
            team_id=HOME_TEAM,
            is_home=True,
            is_starter=True,
            runs_1st=0,
        )
    )
    session.flush()

    detail = games_queries.game_detail(session, game.game_pk)

    assert len(detail.home_pitcher.recent_starts) == 1
    start = detail.home_pitcher.recent_starts[0]
    assert start.game_pk == earlier.game_pk
    assert start.opponent == "NYY"  # the home starter's opponent that day
    assert start.nrfi is True


# --- weather / odds (M8.5) --------------------------------------------


def test_game_detail_weather_is_none_until_captured(session, champion):
    _teams_and_pitchers(session)
    game = _game(session)
    session.add(_prediction(game.game_pk))
    session.flush()

    detail = games_queries.game_detail(session, game.game_pk)

    assert detail.weather is None
    assert detail.odds is None


def test_game_detail_includes_captured_weather_and_odds(session, champion):
    _teams_and_pitchers(session)
    captured = dt.datetime(2026, 8, 18, 12, 0, tzinfo=dt.timezone.utc)
    game = _game(
        session,
        weather_temp_f=68.5,
        weather_conditions="Clear",
        weather_wind_mph=6.0,
        weather_wind_direction_deg=210,
        weather_captured_at=captured,
        home_moneyline=-150,
        away_moneyline=130,
        odds_bookmaker="DraftKings",
        odds_captured_at=captured,
    )
    session.add(_prediction(game.game_pk))
    session.flush()

    detail = games_queries.game_detail(session, game.game_pk)

    assert detail.weather.temp_f == pytest.approx(68.5)
    assert detail.weather.conditions == "Clear"
    assert detail.weather.wind_direction_deg == 210
    assert detail.odds.home_moneyline == -150
    assert detail.odds.away_moneyline == 130
    assert detail.odds.bookmaker == "DraftKings"


def test_games_for_date_summary_includes_weather_but_not_odds_field(session, champion):
    """Dashboard rows show a weather summary (requirements.md); odds are a
    game-detail-only field.
    """
    _teams_and_pitchers(session)
    game = _game(
        session,
        weather_temp_f=72.0,
        weather_conditions="Sunny",
        weather_wind_mph=4.0,
        weather_captured_at=dt.datetime(2026, 8, 18, 12, 0, tzinfo=dt.timezone.utc),
    )
    session.add(_prediction(game.game_pk))
    session.flush()

    rows = games_queries.games_for_date(session, GAME_DATE)

    assert rows[0].weather.temp_f == pytest.approx(72.0)
    assert not hasattr(rows[0], "odds")


def test_game_detail_recent_starts_caps_at_five(session, champion):
    _teams_and_pitchers(session)
    game = _game(session, game_pk=1000)
    session.add(_prediction(game.game_pk))

    for i in range(7):
        past = Game(
            game_pk=100 + i,
            game_date=GAME_DATE - dt.timedelta(days=2 * (i + 1)),
            season=2026,
            home_team_id=HOME_TEAM,
            away_team_id=AWAY_TEAM,
            status="Final",
            nrfi=True,
        )
        session.add(past)
        session.flush()
        session.add(
            PitcherGameStats(
                game_pk=past.game_pk,
                pitcher_id=HOME_SP,
                team_id=HOME_TEAM,
                is_home=True,
                is_starter=True,
                runs_1st=0,
            )
        )
    session.flush()

    detail = games_queries.game_detail(session, game.game_pk)

    assert len(detail.home_pitcher.recent_starts) == 5
    # Most recent first.
    dates = [s.game_date for s in detail.home_pitcher.recent_starts]
    assert dates == sorted(dates, reverse=True)
