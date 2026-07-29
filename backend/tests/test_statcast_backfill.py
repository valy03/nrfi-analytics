"""Unit tests for the M2 Statcast backfill.

pybaseball.statcast is mocked with a small synthetic pitch-level frame, so
these tests are deterministic and offline. They cover label derivation,
regular-season filtering, month chunking, parquet caching, and idempotent
re-runs. A real end-to-end pull is verified manually (see README M2 section).
"""

import datetime as dt

import pandas as pd
import pytest

from app.collection import statcast_backfill as sb
from app.collection.statcast_backfill import (
    StatcastBackfillError,
    derive_game_labels,
    fetch_statcast_chunk,
    run_backfill,
    _month_chunks,
)


def _pitch(game_pk, date, inning, post_away, post_home, game_type="R",
           away="NYY", home="BOS"):
    """One synthetic Statcast pitch row (only the columns we use)."""
    return {
        "game_pk": game_pk,
        "game_date": date,
        "game_type": game_type,
        "away_team": away,
        "home_team": home,
        "inning": inning,
        "inning_topbot": "Top",
        "post_away_score": post_away,
        "post_home_score": post_home,
    }


# Game 100: no first-inning runs -> NRFI. (A 2nd-inning run must be ignored.)
# Game 200: away scores 1 in the 1st -> YRFI.
# Game 300: spring training (game_type "S") -> filtered out by default.
SYNTHETIC = pd.DataFrame(
    [
        _pitch(100, "2023-04-01", 1, 0, 0),
        _pitch(100, "2023-04-01", 1, 0, 0),
        _pitch(100, "2023-04-01", 2, 3, 0),  # 2nd-inning run, ignored
        _pitch(200, "2023-04-01", 1, 0, 0),
        _pitch(200, "2023-04-01", 1, 1, 0),  # away scores in the 1st
        _pitch(300, "2023-03-05", 1, 5, 4, game_type="S"),
    ]
)


def test_derive_labels_nrfi_and_yrfi():
    games = derive_game_labels(SYNTHETIC)

    assert list(games.columns) == sb.GAME_COLUMNS
    # Spring-training game 300 excluded by default.
    assert set(games["game_pk"]) == {100, 200}

    g100 = games[games["game_pk"] == 100].iloc[0]
    assert g100["away_runs_1st"] == 0 and g100["home_runs_1st"] == 0
    assert g100["first_inning_runs"] == 0
    assert g100["nrfi"] == 1
    assert g100["season"] == 2023

    g200 = games[games["game_pk"] == 200].iloc[0]
    assert g200["away_runs_1st"] == 1 and g200["home_runs_1st"] == 0
    assert g200["first_inning_runs"] == 1
    assert g200["nrfi"] == 0


def test_include_postseason_keeps_non_regular_games():
    games = derive_game_labels(SYNTHETIC, regular_season_only=False)
    assert set(games["game_pk"]) == {100, 200, 300}


def test_empty_input_returns_empty_with_columns():
    games = derive_game_labels(pd.DataFrame())
    assert list(games.columns) == sb.GAME_COLUMNS
    assert games.empty


def test_month_chunks_splits_by_calendar_month():
    chunks = _month_chunks(dt.date(2023, 3, 15), dt.date(2023, 4, 20))
    assert chunks == [
        ("2023-03-15", "2023-03-31"),
        ("2023-04-01", "2023-04-20"),
    ]


def test_month_chunks_skips_offseason():
    # Jan/Feb are outside SEASON_MONTHS -> nothing to pull.
    assert _month_chunks(dt.date(2023, 1, 1), dt.date(2023, 2, 28)) == []


def test_month_chunks_rejects_reversed_range():
    with pytest.raises(StatcastBackfillError, match="after end"):
        _month_chunks(dt.date(2023, 5, 1), dt.date(2023, 4, 1))


def test_chunk_is_cached_and_not_redownloaded(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_statcast(start_dt, end_dt):
        calls["n"] += 1
        return SYNTHETIC.copy()

    monkeypatch.setattr(sb.pybaseball, "statcast", fake_statcast)

    df1 = fetch_statcast_chunk("2023-04-01", "2023-04-30", tmp_path)
    assert calls["n"] == 1
    assert (tmp_path / "statcast_2023-04-01_2023-04-30.parquet").exists()

    # Second call for the same range reads the cache, no new download.
    df2 = fetch_statcast_chunk("2023-04-01", "2023-04-30", tmp_path)
    assert calls["n"] == 1
    assert len(df1) == len(df2)


def test_chunk_retries_transient_failure_then_succeeds(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky_statcast(start_dt, end_dt):
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts drop the connection
            raise ConnectionError("IncompleteRead: connection broken")
        return SYNTHETIC.copy()

    monkeypatch.setattr(sb.pybaseball, "statcast", flaky_statcast)

    df = fetch_statcast_chunk(
        "2020-09-01", "2020-09-30", tmp_path, retries=4, retry_wait=0
    )
    assert calls["n"] == 3  # failed twice, succeeded on the third
    assert not df.empty
    assert (tmp_path / "statcast_2020-09-01_2020-09-30.parquet").exists()


def test_chunk_raises_after_exhausting_retries(tmp_path, monkeypatch):
    def always_fails(start_dt, end_dt):
        raise ConnectionError("IncompleteRead: connection broken")

    monkeypatch.setattr(sb.pybaseball, "statcast", always_fails)

    with pytest.raises(StatcastBackfillError, match="after 3 attempts"):
        fetch_statcast_chunk(
            "2020-09-01", "2020-09-30", tmp_path, retries=3, retry_wait=0
        )
    # Nothing cached on total failure.
    assert not (tmp_path / "statcast_2020-09-01_2020-09-30.parquet").exists()


def test_run_backfill_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sb.pybaseball, "statcast", lambda start_dt, end_dt: SYNTHETIC.copy()
    )

    first = run_backfill(dt.date(2023, 4, 1), dt.date(2023, 4, 30), tmp_path)
    second = run_backfill(dt.date(2023, 4, 1), dt.date(2023, 4, 30), tmp_path)

    # Same games both times; no duplication on re-run.
    assert len(first) == len(second) == 2
    assert second["game_pk"].is_unique

    processed = pd.read_parquet(tmp_path / "processed" / "nrfi_games.parquet")
    assert len(processed) == 2