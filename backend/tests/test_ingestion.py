"""Tests for the M3 ingestion loaders.

The MLB Stats API and the M2 parquet are both stubbed, so these run offline
and deterministically. The through-line is the M3 exit criterion: loading
the same data twice must not duplicate or clobber anything.
"""

import datetime as dt

import pandas as pd
import pytest

from app.collection import mlb_stats
from app.collection.mlb_stats import Game as ScheduleGame
from app.ingestion import daily, historical, teams as teams_ingest
from app.ingestion.upsert import upsert_rows
from app.models import Game, Pitcher, Team

TEAMS_PAYLOAD = {
    "teams": [
        {
            "id": 147,
            "name": "New York Yankees",
            "abbreviation": "NYY",
            "teamCode": "nya",
            "league": {"name": "American League"},
            "division": {"name": "American League East"},
        },
        {
            "id": 111,
            "name": "Boston Red Sox",
            "abbreviation": "BOS",
            "teamCode": "bos",
            "league": {"name": "American League"},
            "division": {"name": "American League East"},
        },
        {
            "id": 133,
            "name": "Athletics",
            "abbreviation": "ATH",
            "teamCode": "ath",
            "league": {"name": "American League"},
            "division": {"name": "American League West"},
        },
    ]
}

# Two labeled games in the shape the M2 backfill writes.
STATCAST_GAMES = pd.DataFrame(
    [
        {
            "game_pk": 745804,
            "game_date": pd.Timestamp("2025-07-01"),
            "season": 2025,
            "game_type": "R",
            "away_team": "NYY",
            "home_team": "BOS",
            "away_runs_1st": 0,
            "home_runs_1st": 0,
            "first_inning_runs": 0,
            "nrfi": 1,
        },
        {
            "game_pk": 745805,
            "game_date": pd.Timestamp("2025-07-02"),
            "season": 2025,
            "game_type": "R",
            "away_team": "ATH",
            "home_team": "NYY",
            "away_runs_1st": 2,
            "home_runs_1st": 1,
            "first_inning_runs": 3,
            "nrfi": 0,
        },
    ]
)


def _schedule_game(**overrides) -> ScheduleGame:
    base = dict(
        game_id=745804,
        status="Scheduled",
        away_team="New York Yankees",
        home_team="Boston Red Sox",
        away_team_id=147,
        home_team_id=111,
        venue="Fenway Park",
        start_time_utc="2025-07-01T23:05:00Z",
        away_probable_pitcher="Gerrit Cole",
        home_probable_pitcher="Brayan Bello",
        away_score=None,
        home_score=None,
        doubleheader=False,
        game_num=1,
        game_date="2025-07-01",
        game_type="R",
        venue_id=3,
        away_probable_pitcher_id=543037,
        home_probable_pitcher_id=678394,
    )
    base.update(overrides)
    return ScheduleGame(**base)


@pytest.fixture
def seeded(session, monkeypatch):
    """A session with the team reference table populated."""
    monkeypatch.setattr(
        teams_ingest.statsapi, "get", lambda *a, **kw: TEAMS_PAYLOAD
    )
    teams_ingest.seed_teams(session)
    return session


# --- team seeding ----------------------------------------------------------


def test_seed_teams_is_idempotent(session, monkeypatch):
    monkeypatch.setattr(
        teams_ingest.statsapi, "get", lambda *a, **kw: TEAMS_PAYLOAD
    )

    first = teams_ingest.seed_teams(session)
    second = teams_ingest.seed_teams(session)

    assert first.inserted == 3 and first.updated == 0
    assert second.inserted == 0 and second.updated == 0
    assert session.query(Team).count() == 3


def test_seed_teams_updates_a_renamed_club(seeded, monkeypatch):
    renamed = {"teams": [dict(TEAMS_PAYLOAD["teams"][2], name="Las Vegas Athletics")]}
    monkeypatch.setattr(teams_ingest.statsapi, "get", lambda *a, **kw: renamed)

    counts = teams_ingest.seed_teams(seeded)

    assert counts.updated == 1
    assert seeded.get(Team, 133).name == "Las Vegas Athletics"


def test_abbreviation_lookup_resolves_legacy_codes(seeded):
    lookup = teams_ingest.team_id_by_abbreviation(seeded)
    assert lookup["ATH"] == 133
    assert lookup["OAK"] == 133  # pre-2025 Oakland code still resolves
    assert lookup["NYY"] == 147


# --- historical (M2 parquet -> games) --------------------------------------


def test_historical_load_maps_labels(seeded, monkeypatch, tmp_path):
    path = tmp_path / "nrfi_games.parquet"
    STATCAST_GAMES.to_parquet(path, index=False)

    counts = historical.load_historical(seeded, path, progress=False)

    assert counts.inserted == 2
    game = seeded.get(Game, 745804)
    assert game.game_date == dt.date(2025, 7, 1)
    assert game.season == 2025
    assert game.away_team_id == 147 and game.home_team_id == 111
    assert game.nrfi is True
    assert seeded.get(Game, 745805).nrfi is False


def test_historical_load_is_idempotent(seeded, tmp_path):
    path = tmp_path / "nrfi_games.parquet"
    STATCAST_GAMES.to_parquet(path, index=False)

    historical.load_historical(seeded, path, progress=False)
    second = historical.load_historical(seeded, path, progress=False)

    assert second.inserted == 0 and second.updated == 0
    assert seeded.query(Game).count() == 2


def test_historical_load_filters_by_season(seeded, tmp_path):
    path = tmp_path / "nrfi_games.parquet"
    STATCAST_GAMES.to_parquet(path, index=False)

    counts = historical.load_historical(seeded, path, season=2024, progress=False)

    assert counts.total == 0
    assert seeded.query(Game).count() == 0


def test_unmapped_abbreviation_is_an_error_not_a_silent_drop(seeded, tmp_path):
    rogue = STATCAST_GAMES.copy()
    rogue.loc[0, "away_team"] = "MTL"
    path = tmp_path / "nrfi_games.parquet"
    rogue.to_parquet(path, index=False)

    with pytest.raises(historical.HistoricalIngestionError, match="MTL"):
        historical.load_historical(seeded, path, progress=False)


def test_missing_dataset_points_at_the_backfill(seeded, tmp_path):
    with pytest.raises(historical.HistoricalIngestionError, match="M2 backfill"):
        historical.load_historical(seeded, tmp_path / "nope.parquet")


# --- daily (M1 schedule -> games) ------------------------------------------


def test_daily_load_inserts_games_and_pitchers(seeded, monkeypatch):
    monkeypatch.setattr(
        daily, "fetch_schedule", lambda *a, **kw: [_schedule_game()]
    )

    pitchers, games, labeled = daily.load_date(seeded, "2025-07-01")

    assert pitchers.inserted == 2
    assert games.inserted == 1
    assert labeled == 0  # not final yet

    game = seeded.get(Game, 745804)
    assert game.status == "Scheduled"
    assert game.venue_name == "Fenway Park"
    assert game.away_probable_pitcher.full_name == "Gerrit Cole"
    assert game.start_time_utc == dt.datetime(
        2025, 7, 1, 23, 5, tzinfo=dt.timezone.utc
    )
    assert game.nrfi is None


def test_daily_load_is_idempotent(seeded, monkeypatch):
    monkeypatch.setattr(
        daily, "fetch_schedule", lambda *a, **kw: [_schedule_game()]
    )

    daily.load_date(seeded, "2025-07-01")
    _, games, _ = daily.load_date(seeded, "2025-07-01")

    assert games.inserted == 0 and games.updated == 0
    assert seeded.query(Game).count() == 1
    assert seeded.query(Pitcher).count() == 2


def test_daily_load_labels_finished_games(seeded, monkeypatch):
    final = _schedule_game(status="Final", away_score=4, home_score=2)
    monkeypatch.setattr(daily, "fetch_schedule", lambda *a, **kw: [final])
    monkeypatch.setattr(
        daily,
        "fetch_first_inning_result",
        lambda game_id: mlb_stats.FirstInningResult(game_id, away_runs=0, home_runs=0),
    )

    _, _, labeled = daily.load_date(seeded, "2025-07-01")

    game = seeded.get(Game, 745804)
    assert labeled == 1
    assert game.nrfi is True
    assert game.first_inning_runs == 0
    assert game.away_score == 4 and game.home_score == 2


def test_already_labeled_games_are_not_re_fetched(seeded, monkeypatch):
    final = _schedule_game(status="Final", away_score=4, home_score=2)
    monkeypatch.setattr(daily, "fetch_schedule", lambda *a, **kw: [final])

    calls = {"n": 0}

    def counting_linescore(game_id):
        calls["n"] += 1
        return mlb_stats.FirstInningResult(game_id, away_runs=0, home_runs=0)

    monkeypatch.setattr(daily, "fetch_first_inning_result", counting_linescore)

    daily.load_date(seeded, "2025-07-01")
    daily.load_date(seeded, "2025-07-01")

    assert calls["n"] == 1  # second run skips the already-labeled game


def test_suspended_game_stays_unlabeled(seeded, monkeypatch):
    final = _schedule_game(status="Final")
    monkeypatch.setattr(daily, "fetch_schedule", lambda *a, **kw: [final])
    monkeypatch.setattr(daily, "fetch_first_inning_result", lambda game_id: None)

    _, _, labeled = daily.load_date(seeded, "2025-07-01")

    assert labeled == 0
    assert seeded.get(Game, 745804).nrfi is None


def test_unannounced_pitchers_are_skipped(seeded, monkeypatch):
    tbd = _schedule_game(
        away_probable_pitcher=None,
        away_probable_pitcher_id=None,
        home_probable_pitcher=None,
        home_probable_pitcher_id=None,
    )
    monkeypatch.setattr(daily, "fetch_schedule", lambda *a, **kw: [tbd])

    pitchers, games, _ = daily.load_date(seeded, "2025-07-01")

    assert pitchers.total == 0
    assert games.inserted == 1
    assert seeded.get(Game, 745804).away_probable_pitcher_id is None


def test_empty_slate_is_a_no_op(seeded, monkeypatch):
    monkeypatch.setattr(daily, "fetch_schedule", lambda *a, **kw: [])

    pitchers, games, labeled = daily.load_date(seeded, "2025-12-25")

    assert (pitchers.total, games.total, labeled) == (0, 0, 0)


# --- the two sources sharing one row ---------------------------------------


def test_daily_enriches_a_statcast_row_without_erasing_its_label(
    seeded, monkeypatch, tmp_path
):
    """The core merge case: Statcast labels the game, the schedule feed adds
    venue/pitchers, and neither wipes out the other's columns."""
    path = tmp_path / "nrfi_games.parquet"
    STATCAST_GAMES.to_parquet(path, index=False)
    historical.load_historical(seeded, path, progress=False)

    # The schedule feed knows nothing about first-inning runs.
    monkeypatch.setattr(
        daily, "fetch_schedule", lambda *a, **kw: [_schedule_game(status="Final")]
    )
    monkeypatch.setattr(daily, "fetch_first_inning_result", lambda game_id: None)

    _, games, _ = daily.load_date(seeded, "2025-07-01")

    game = seeded.get(Game, 745804)
    assert games.inserted == 0 and games.updated == 1
    assert game.venue_name == "Fenway Park"  # added by the daily loader
    assert game.nrfi is True  # preserved from the backfill
    assert game.first_inning_runs == 0


# --- the upsert primitive itself -------------------------------------------


def test_upsert_updates_only_changed_columns(seeded):
    upsert_rows(seeded, Pitcher, [{"id": 1, "full_name": "A. Pitcher"}], ["id"])
    counts = upsert_rows(
        seeded, Pitcher, [{"id": 1, "full_name": "A. Pitcher", "throws": "L"}], ["id"]
    )

    assert counts.updated == 1
    assert seeded.get(Pitcher, 1).throws == "L"


def test_upsert_never_blanks_a_value_with_none(seeded):
    upsert_rows(seeded, Pitcher, [{"id": 1, "full_name": "A. Pitcher", "throws": "R"}], ["id"])
    counts = upsert_rows(
        seeded, Pitcher, [{"id": 1, "full_name": "A. Pitcher", "throws": None}], ["id"]
    )

    assert counts.skipped == 1
    assert seeded.get(Pitcher, 1).throws == "R"


def test_upsert_dedupes_within_a_batch(seeded):
    counts = upsert_rows(
        seeded,
        Pitcher,
        [{"id": 1, "full_name": "First"}, {"id": 1, "full_name": "Last"}],
        ["id"],
    )

    assert counts.inserted == 1
    assert seeded.get(Pitcher, 1).full_name == "Last"


def test_upsert_handles_ragged_payloads(seeded):
    counts = upsert_rows(
        seeded,
        Pitcher,
        [{"id": 1, "full_name": "No Throws"}, {"id": 2, "full_name": "Lefty", "throws": "L"}],
        ["id"],
    )

    assert counts.inserted == 2
    assert seeded.get(Pitcher, 1).throws is None
    assert seeded.get(Pitcher, 2).throws == "L"
