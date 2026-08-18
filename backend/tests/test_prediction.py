"""Tests for the M7 daily prediction job.

``infer.predict`` is tested against a stub model — no real joblib artifact,
no database — same spirit as the M5/M6 tests exercising real logic on
synthetic inputs. ``store.save_predictions`` and ``job.eligible_games`` run
against the in-memory SQLite ``session`` fixture with real ORM rows, the
same pattern test_models.py / test_ingestion.py use. ``job.run`` is
exercised with the network call and the feature/inference steps stubbed at
the point job.py imports them — mirroring how test_ingestion.py stubs
``app.ingestion.daily.fetch_schedule`` rather than the real MLB API.
"""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from app.features import config as fcfg
from app.ingestion.upsert import UpsertCounts
from app.models import Game, Pitcher, Prediction, Team
from app.prediction import infer, job
from app.prediction.store import save_predictions
from app.training import config as tcfg

# --- infer.predict -----------------------------------------------------


class _StubModel:
    """predict_proba returning a fixed NRFI probability per row."""

    def __init__(self, probas):
        self.probas = np.asarray(probas)

    def predict_proba(self, X):
        return np.column_stack([1 - self.probas, self.probas])


def _matrix(game_pks, feature_value=0.5):
    rows = []
    for pk in game_pks:
        row = {col: feature_value for col in fcfg.FEATURE_COLUMNS}
        row["game_pk"] = pk
        rows.append(row)
    return pd.DataFrame(rows)


def test_predict_returns_nothing_for_an_empty_matrix():
    assert infer.predict(pd.DataFrame(columns=["game_pk", *fcfg.FEATURE_COLUMNS])) == []


def test_predict_maps_probability_to_label_and_confidence(monkeypatch):
    monkeypatch.setattr(
        infer, "load_champion", lambda: (_StubModel([0.8, 0.2]), "logreg", "m5-v1")
    )
    matrix = _matrix([111, 222])

    rows = infer.predict(matrix)

    assert rows[0]["game_pk"] == 111
    assert rows[0]["model_name"] == "logreg"
    assert rows[0]["model_version"] == "m5-v1"
    assert rows[0]["predicted_label"] == "NRFI"
    assert rows[0]["nrfi_probability"] == pytest.approx(0.8)
    assert rows[0]["yrfi_probability"] == pytest.approx(0.2)
    assert rows[0]["confidence"] == pytest.approx(0.6)  # |2*0.8 - 1|
    assert rows[0]["features"]["home_sp_nrfi_rate"] == pytest.approx(0.5)

    assert rows[1]["game_pk"] == 222
    assert rows[1]["predicted_label"] == "YRFI"
    assert rows[1]["confidence"] == pytest.approx(0.6)  # |2*0.2 - 1|


def test_predict_ties_at_exactly_half_go_to_nrfi(monkeypatch):
    monkeypatch.setattr(infer, "load_champion", lambda: (_StubModel([0.5]), "logreg", "v1"))

    rows = infer.predict(_matrix([111]))

    assert rows[0]["predicted_label"] == "NRFI"
    assert rows[0]["confidence"] == pytest.approx(0.0)


def test_load_champion_raises_a_clear_error_when_no_artifact_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(tcfg, "CHAMPION_PATH", tmp_path / "missing.joblib")

    with pytest.raises(infer.ChampionNotFoundError):
        infer.load_champion()


# --- store.save_predictions ---------------------------------------------


def _team_and_game(session, game_pk=745804):
    away = Team(id=147, name="New York Yankees", abbreviation="NYY")
    home = Team(id=111, name="Boston Red Sox", abbreviation="BOS")
    session.add_all([away, home])
    session.flush()
    game = Game(
        game_pk=game_pk,
        game_date=dt.date(2025, 7, 1),
        season=2025,
        away_team_id=away.id,
        home_team_id=home.id,
    )
    session.add(game)
    session.flush()
    return game


def _prediction_row(game_pk, model_version="m5-v1", p=0.6):
    return {
        "game_pk": game_pk,
        "model_name": "logreg",
        "model_version": model_version,
        "predicted_label": "NRFI" if p >= 0.5 else "YRFI",
        "nrfi_probability": p,
        "yrfi_probability": 1 - p,
        "confidence": abs(2 * p - 1),
        "features": {"a": 1.0},
    }


def test_save_predictions_inserts_a_new_row(session):
    game = _team_and_game(session)

    counts = save_predictions(session, [_prediction_row(game.game_pk)])

    assert counts.inserted == 1
    stored = session.query(Prediction).one()
    assert stored.model_version == "m5-v1"
    assert stored.nrfi_probability == pytest.approx(0.6)


def test_save_predictions_is_idempotent(session):
    game = _team_and_game(session)
    save_predictions(session, [_prediction_row(game.game_pk, p=0.6)])

    counts = save_predictions(session, [_prediction_row(game.game_pk, p=0.6)])

    assert counts.inserted == 0
    assert counts.skipped == 1
    assert session.query(Prediction).count() == 1


def test_save_predictions_updates_a_changed_probability_in_place(session):
    game = _team_and_game(session)
    save_predictions(session, [_prediction_row(game.game_pk, p=0.6)])

    counts = save_predictions(session, [_prediction_row(game.game_pk, p=0.7)])

    assert counts.updated == 1
    stored = session.query(Prediction).one()
    assert stored.nrfi_probability == pytest.approx(0.7)


def test_save_predictions_keeps_both_model_versions_side_by_side(session):
    game = _team_and_game(session)
    save_predictions(session, [_prediction_row(game.game_pk, model_version="m5-v1")])

    counts = save_predictions(
        session, [_prediction_row(game.game_pk, model_version="m6-xgb-v1")]
    )

    assert counts.inserted == 1
    assert session.query(Prediction).count() == 2


# --- job.eligible_games ---------------------------------------------------


def test_eligible_games_filters_started_and_starterless_games(session):
    away = Team(id=147, name="New York Yankees", abbreviation="NYY")
    home = Team(id=111, name="Boston Red Sox", abbreviation="BOS")
    session.add_all([away, home])
    session.add_all([Pitcher(id=1, full_name="A"), Pitcher(id=2, full_name="B")])
    session.flush()

    date = dt.date(2026, 8, 17)

    def _game(game_pk, game_date, status, home_sp=2, away_sp=1):
        return Game(
            game_pk=game_pk,
            game_date=game_date,
            season=game_date.year,
            away_team_id=away.id,
            home_team_id=home.id,
            status=status,
            home_probable_pitcher_id=home_sp,
            away_probable_pitcher_id=away_sp,
        )

    ready = _game(1, date, "Scheduled")
    no_starters = _game(2, date, "Scheduled", home_sp=None, away_sp=None)
    started = _game(3, date, "In Progress")
    tomorrow = _game(4, date + dt.timedelta(days=1), "Scheduled")
    session.add_all([ready, no_starters, started, tomorrow])
    session.flush()

    game_pks, skipped_started, skipped_no_starters = job.eligible_games(session, date)

    assert game_pks == [1]
    assert skipped_started == 1
    assert skipped_no_starters == 1


def test_eligible_games_returns_nothing_for_a_slate_with_no_games(session):
    game_pks, skipped_started, skipped_no_starters = job.eligible_games(
        session, dt.date(2026, 8, 17)
    )

    assert game_pks == []
    assert skipped_started == 0
    assert skipped_no_starters == 0


# --- job.run orchestration -------------------------------------------------


def test_run_skips_feature_and_inference_steps_when_nothing_is_eligible(
    session, monkeypatch
):
    monkeypatch.setattr(job, "load_date", lambda *a, **kw: None)
    monkeypatch.setattr(job, "eligible_games", lambda *a, **kw: ([], 2, 1))

    def _fail(*a, **kw):
        raise AssertionError("features_for_games should not run with nothing eligible")

    monkeypatch.setattr(job, "features_for_games", _fail)

    result = job.run(session, dt.date(2026, 8, 17))

    assert result == {
        "date": "2026-08-17",
        "eligible": 0,
        "skipped_started": 2,
        "skipped_no_starters": 1,
        "predicted": 0,
    }


def test_run_wires_features_through_predict_and_store(session, monkeypatch):
    monkeypatch.setattr(job, "load_date", lambda *a, **kw: None)
    monkeypatch.setattr(job, "eligible_games", lambda *a, **kw: ([111, 222], 0, 0))

    fake_matrix = pd.DataFrame({"game_pk": [111, 222]})
    monkeypatch.setattr(
        job,
        "features_for_games",
        lambda s, pks: fake_matrix if pks == [111, 222] else pd.DataFrame(),
    )

    fake_rows = [
        {
            "game_pk": pk,
            "model_name": "logreg",
            "model_version": "m5-v1",
            "predicted_label": "NRFI",
            "nrfi_probability": 0.6,
            "yrfi_probability": 0.4,
            "confidence": 0.2,
            "features": {},
        }
        for pk in (111, 222)
    ]
    monkeypatch.setattr(
        job, "predict", lambda matrix: fake_rows if matrix is fake_matrix else []
    )

    saved = {}

    def fake_save(session, rows):
        saved["rows"] = rows
        return UpsertCounts(inserted=len(rows))

    monkeypatch.setattr(job, "save_predictions", fake_save)

    result = job.run(session, dt.date(2026, 8, 17))

    assert result["eligible"] == 2
    assert result["predicted"] == 2
    assert saved["rows"] == fake_rows
    assert "2 inserted" in result["upsert"]
