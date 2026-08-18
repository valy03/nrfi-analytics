"""Tests for the M8 historical-results queries (app.queries.history)."""

import datetime as dt

import pytest

from app.models import Game, Prediction, PredictionResult, Team
from app.queries import history as history_queries

HOME_TEAM, AWAY_TEAM = 111, 147


def _teams(session):
    session.add_all(
        [
            Team(id=HOME_TEAM, name="Boston Red Sox", abbreviation="BOS"),
            Team(id=AWAY_TEAM, name="New York Yankees", abbreviation="NYY"),
        ]
    )
    session.flush()


def _game(session, game_pk, date, nrfi=None):
    game = Game(
        game_pk=game_pk,
        game_date=date,
        season=date.year,
        home_team_id=HOME_TEAM,
        away_team_id=AWAY_TEAM,
        status="Final" if nrfi is not None else "Scheduled",
        nrfi=nrfi,
    )
    session.add(game)
    session.flush()
    return game


def _prediction(game_pk, model_version="m5-v1", label="NRFI"):
    p = 0.6 if label == "NRFI" else 0.4
    pred = Prediction(
        game_pk=game_pk,
        model_name="logreg",
        model_version=model_version,
        predicted_label=label,
        nrfi_probability=p,
        yrfi_probability=1 - p,
        confidence=0.2,
    )
    return pred


def _grade(session, prediction, actual_label):
    session.flush()
    session.add(
        PredictionResult(
            prediction_id=prediction.id,
            game_pk=prediction.game_pk,
            actual_label=actual_label,
            correct=(actual_label == prediction.predicted_label),
        )
    )


# --- prediction_history --------------------------------------------------


def test_history_includes_null_outcome_for_an_ungraded_prediction(session):
    _teams(session)
    game = _game(session, 1, dt.date(2026, 8, 18))
    session.add(_prediction(game.game_pk))
    session.flush()

    items = history_queries.prediction_history(session)

    assert len(items) == 1
    assert items[0].actual_label is None
    assert items[0].correct is None


def test_history_includes_graded_outcome(session):
    _teams(session)
    game = _game(session, 1, dt.date(2026, 8, 17), nrfi=True)
    pred = _prediction(game.game_pk, label="NRFI")
    session.add(pred)
    _grade(session, pred, "NRFI")

    items = history_queries.prediction_history(session)

    assert items[0].actual_label == "NRFI"
    assert items[0].correct is True


def test_history_orders_most_recent_game_first(session):
    _teams(session)
    older = _game(session, 1, dt.date(2026, 8, 1))
    newer = _game(session, 2, dt.date(2026, 8, 18))
    session.add_all([_prediction(older.game_pk), _prediction(newer.game_pk)])
    session.flush()

    items = history_queries.prediction_history(session)

    assert [i.game_pk for i in items] == [newer.game_pk, older.game_pk]


def test_history_filters_by_date_range(session):
    _teams(session)
    in_range = _game(session, 1, dt.date(2026, 8, 10))
    out_of_range = _game(session, 2, dt.date(2026, 7, 1))
    session.add_all([_prediction(in_range.game_pk), _prediction(out_of_range.game_pk)])
    session.flush()

    items = history_queries.prediction_history(
        session, start_date=dt.date(2026, 8, 1), end_date=dt.date(2026, 8, 31)
    )

    assert [i.game_pk for i in items] == [in_range.game_pk]


def test_history_filters_by_team(session):
    _teams(session)
    game = _game(session, 1, dt.date(2026, 8, 18))
    session.add(_prediction(game.game_pk))
    session.flush()

    assert len(history_queries.prediction_history(session, team="bos")) == 1
    assert history_queries.prediction_history(session, team="LAD") == []


def test_history_filters_by_model_version(session):
    _teams(session)
    game = _game(session, 1, dt.date(2026, 8, 18))
    session.add_all(
        [
            _prediction(game.game_pk, model_version="m5-v1"),
            _prediction(game.game_pk, model_version="m6-xgb-v1"),
        ]
    )
    session.flush()

    items = history_queries.prediction_history(session, model_version="m6-xgb-v1")

    assert len(items) == 1
    assert items[0].model_version == "m6-xgb-v1"


def test_history_respects_limit_and_offset(session):
    _teams(session)
    for i in range(5):
        game = _game(session, i, dt.date(2026, 8, 1) + dt.timedelta(days=i))
        session.add(_prediction(game.game_pk))
    session.flush()

    page1 = history_queries.prediction_history(session, limit=2, offset=0)
    page2 = history_queries.prediction_history(session, limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert {i.game_pk for i in page1}.isdisjoint({i.game_pk for i in page2})


# --- accuracy_report -------------------------------------------------------


def test_accuracy_report_is_empty_when_nothing_is_graded(session):
    report = history_queries.accuracy_report(session)

    assert report.overall.total == 0
    assert report.overall.accuracy is None
    assert report.monthly == []
    assert report.yearly == []


def test_accuracy_report_computes_overall_rate(session):
    _teams(session)
    g1 = _game(session, 1, dt.date(2026, 7, 15), nrfi=True)
    g2 = _game(session, 2, dt.date(2026, 7, 16), nrfi=False)
    p1 = _prediction(g1.game_pk, label="NRFI")
    p2 = _prediction(g2.game_pk, label="NRFI")
    session.add_all([p1, p2])
    _grade(session, p1, "NRFI")
    _grade(session, p2, "YRFI")

    report = history_queries.accuracy_report(session)

    assert report.overall.total == 2
    assert report.overall.correct == 1
    assert report.overall.accuracy == pytest.approx(0.5)
    assert report.overall.win_rate == report.overall.accuracy


def test_accuracy_report_buckets_by_month_and_year(session):
    _teams(session)
    july = _game(session, 1, dt.date(2026, 7, 15), nrfi=True)
    august = _game(session, 2, dt.date(2026, 8, 15), nrfi=True)
    p_july = _prediction(july.game_pk, label="NRFI")
    p_august = _prediction(august.game_pk, label="NRFI")
    session.add_all([p_july, p_august])
    _grade(session, p_july, "NRFI")
    _grade(session, p_august, "NRFI")

    report = history_queries.accuracy_report(session)

    assert [b.period for b in report.monthly] == ["2026-07", "2026-08"]
    assert [b.period for b in report.yearly] == ["2026"]
    assert report.yearly[0].total == 2


def test_accuracy_report_can_be_scoped_to_a_model_version(session):
    _teams(session)
    game = _game(session, 1, dt.date(2026, 7, 15), nrfi=True)
    good = _prediction(game.game_pk, label="NRFI", model_version="m6-xgb-v1")
    bad = _prediction(game.game_pk, label="YRFI", model_version="m5-v1")
    session.add_all([good, bad])
    _grade(session, good, "NRFI")
    _grade(session, bad, "NRFI")

    report = history_queries.accuracy_report(session, model_version="m6-xgb-v1")

    assert report.overall.total == 1
    assert report.overall.correct == 1
