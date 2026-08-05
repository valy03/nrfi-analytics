"""Unit tests for the M1 MLB Stats API collection module.

These mock statsapi.schedule() so the tests are deterministic and don't hit
the network — mapping logic, empty-day handling, unannounced-pitcher
normalization, date conversion, and error wrapping are all exercised here.
A real end-to-end call is verified manually (see README M1 section).
"""

import datetime as dt

import pytest

from app.collection import mlb_stats
from app.collection.mlb_stats import (
    Game,
    MLBStatsAPIError,
    fetch_first_inning_result,
    fetch_probable_pitcher_ids,
    fetch_schedule,
    mlb_today,
)

# A scheduled game with both starters announced.
GAME_WITH_PITCHERS = {
    "game_id": 745804,
    "game_datetime": "2025-07-01T23:05:00Z",
    "status": "Scheduled",
    "away_name": "New York Yankees",
    "home_name": "Boston Red Sox",
    "away_id": 147,
    "home_id": 111,
    "venue_name": "Fenway Park",
    "away_probable_pitcher": "Gerrit Cole",
    "home_probable_pitcher": "Brayan Bello",
    "away_score": "",
    "home_score": "",
    "doubleheader": "N",
    "game_num": 1,
}

# A game where MLB hasn't announced starters yet (empty strings).
GAME_WITHOUT_PITCHERS = {
    "game_id": 745900,
    "game_datetime": "2025-07-01T20:10:00Z",
    "status": "Scheduled",
    "away_name": "Chicago Cubs",
    "home_name": "Milwaukee Brewers",
    "away_id": 112,
    "home_id": 158,
    "venue_name": "American Family Field",
    "away_probable_pitcher": "",
    "home_probable_pitcher": "",
    "away_score": "",
    "home_score": "",
    "doubleheader": "N",
    "game_num": 1,
}

# A finished (past-date) game with a final score.
FINISHED_GAME = {
    "game_id": 700000,
    "game_datetime": "2024-04-10T18:35:00Z",
    "status": "Final",
    "away_name": "Los Angeles Dodgers",
    "home_name": "San Francisco Giants",
    "away_id": 119,
    "home_id": 137,
    "venue_name": "Oracle Park",
    "away_probable_pitcher": "Tyler Glasnow",
    "home_probable_pitcher": "Logan Webb",
    "away_score": 5,
    "home_score": 2,
    "doubleheader": "N",
    "game_num": 1,
}


@pytest.fixture
def fake_schedule(monkeypatch):
    """Patch statsapi.schedule with a canned payload; capture call kwargs."""
    calls = {}

    def _install(payload):
        def _schedule(**kwargs):
            calls.update(kwargs)
            return payload
        monkeypatch.setattr(mlb_stats.statsapi, "schedule", _schedule)
        return calls

    return _install


def test_maps_core_fields(fake_schedule):
    fake_schedule([GAME_WITH_PITCHERS])
    games = fetch_schedule("2025-07-01")

    assert len(games) == 1
    g = games[0]
    assert isinstance(g, Game)
    assert g.game_id == 745804
    assert g.matchup == "New York Yankees @ Boston Red Sox"
    assert g.away_team_id == 147 and g.home_team_id == 111
    assert g.venue == "Fenway Park"
    assert g.start_time_utc == "2025-07-01T23:05:00Z"
    assert g.away_probable_pitcher == "Gerrit Cole"
    assert g.home_probable_pitcher == "Brayan Bello"
    assert g.pitchers_announced is True
    # No score before the game starts.
    assert g.away_score is None and g.home_score is None


def test_unannounced_pitchers_become_none(fake_schedule):
    fake_schedule([GAME_WITHOUT_PITCHERS])
    g = fetch_schedule("2025-07-01")[0]

    assert g.away_probable_pitcher is None
    assert g.home_probable_pitcher is None
    assert g.pitchers_announced is False


def test_finished_game_has_scores(fake_schedule):
    fake_schedule([FINISHED_GAME])
    g = fetch_schedule("2024-04-10")[0]

    assert g.status == "Final"
    assert g.away_score == 5 and g.home_score == 2


def test_no_games_returns_empty_list(fake_schedule):
    fake_schedule([])
    assert fetch_schedule("2025-12-25") == []


def test_iso_date_is_converted_to_api_format(fake_schedule):
    calls = fake_schedule([])
    fetch_schedule("2025-07-01")
    assert calls["date"] == "07/01/2025"


def test_date_object_is_accepted(fake_schedule):
    calls = fake_schedule([])
    fetch_schedule(dt.date(2025, 7, 1))
    assert calls["date"] == "07/01/2025"


def test_default_date_is_today_in_eastern(fake_schedule):
    """MLB's game day is Eastern. On a UTC host late at night the two dates
    disagree, and defaulting to UTC would pull tomorrow's slate."""
    calls = fake_schedule([])
    fetch_schedule()
    assert calls["date"] == mlb_today().strftime("%m/%d/%Y")


def test_mlb_today_tracks_eastern_not_utc():
    eastern_now = dt.datetime.now(mlb_stats.MLB_TIMEZONE)
    assert mlb_today() == eastern_now.date()


def test_invalid_date_raises(fake_schedule):
    fake_schedule([])
    with pytest.raises(MLBStatsAPIError, match="Invalid date"):
        fetch_schedule("July 1st")


def test_api_failure_is_wrapped(monkeypatch):
    def _boom(**kwargs):
        raise ConnectionError("savant is down")

    monkeypatch.setattr(mlb_stats.statsapi, "schedule", _boom)
    with pytest.raises(MLBStatsAPIError, match="Failed to fetch schedule"):
        fetch_schedule("2025-07-01")


# --- probable pitcher ids (M3 needs them as foreign keys) ------------------

HYDRATED_SCHEDULE = {
    "dates": [
        {
            "games": [
                {
                    "gamePk": 745804,
                    "teams": {
                        "away": {"probablePitcher": {"id": 543037}},
                        "home": {"probablePitcher": {"id": 678394}},
                    },
                },
                {  # starters not announced yet
                    "gamePk": 745900,
                    "teams": {"away": {}, "home": {}},
                },
            ]
        }
    ]
}


def test_pitcher_ids_are_extracted_from_the_hydrated_feed(monkeypatch):
    monkeypatch.setattr(
        mlb_stats.statsapi, "get", lambda endpoint, params: HYDRATED_SCHEDULE
    )
    ids = fetch_probable_pitcher_ids("2025-07-01")

    assert ids[745804] == (543037, 678394)
    assert ids[745900] == (None, None)


def test_fetch_schedule_merges_pitcher_ids(fake_schedule, monkeypatch):
    fake_schedule([GAME_WITH_PITCHERS])
    monkeypatch.setattr(
        mlb_stats.statsapi, "get", lambda endpoint, params: HYDRATED_SCHEDULE
    )

    g = fetch_schedule("2025-07-01", with_pitcher_ids=True)[0]

    assert g.away_probable_pitcher_id == 543037
    assert g.home_probable_pitcher_id == 678394
    assert g.away_probable_pitcher == "Gerrit Cole"  # name still mapped


def test_pitcher_ids_are_not_fetched_by_default(fake_schedule, monkeypatch):
    fake_schedule([GAME_WITH_PITCHERS])

    def _should_not_be_called(endpoint, params):
        raise AssertionError("hydrated request made without with_pitcher_ids")

    monkeypatch.setattr(mlb_stats.statsapi, "get", _should_not_be_called)

    g = fetch_schedule("2025-07-01")[0]
    assert g.away_probable_pitcher_id is None


# --- first-inning result (the operational NRFI label) ----------------------


def _linescore(*innings):
    return {"innings": list(innings)}


def test_first_inning_result_reads_the_linescore(monkeypatch):
    monkeypatch.setattr(
        mlb_stats.statsapi,
        "get",
        lambda endpoint, params: _linescore(
            {"num": 1, "away": {"runs": 0}, "home": {"runs": 0}},
            {"num": 2, "away": {"runs": 3}, "home": {"runs": 0}},
        ),
    )
    result = fetch_first_inning_result(745804)

    assert result.away_runs == 0 and result.home_runs == 0
    assert result.total_runs == 0
    assert result.nrfi is True  # the 2nd-inning runs don't count


def test_first_inning_result_detects_yrfi(monkeypatch):
    monkeypatch.setattr(
        mlb_stats.statsapi,
        "get",
        lambda endpoint, params: _linescore(
            {"num": 1, "away": {"runs": 2}, "home": {"runs": 1}}
        ),
    )
    result = fetch_first_inning_result(745804)

    assert result.total_runs == 3
    assert result.nrfi is False


def test_first_inning_still_in_progress_returns_none(monkeypatch):
    # Top of the 1st: the home half hasn't been batted, so no runs key.
    monkeypatch.setattr(
        mlb_stats.statsapi,
        "get",
        lambda endpoint, params: _linescore({"num": 1, "away": {"runs": 0}, "home": {}}),
    )
    assert fetch_first_inning_result(745804) is None


def test_game_with_no_innings_returns_none(monkeypatch):
    monkeypatch.setattr(mlb_stats.statsapi, "get", lambda endpoint, params: _linescore())
    assert fetch_first_inning_result(745804) is None