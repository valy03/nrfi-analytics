"""Tests for the M7 scheduler's timing logic.

``next_run_at`` is the only part of app.prediction.scheduler worth unit
testing — the loop around it is an infinite ``sleep``/``run_once`` cycle
that's exercised by actually running the service, not by pytest.
"""

import datetime as dt

from app.collection.mlb_stats import MLB_TIMEZONE
from app.prediction.scheduler import DEFAULT_RUN_TIME, next_run_at


def test_next_run_is_later_today_when_before_the_run_time():
    now = dt.datetime(2026, 8, 18, 6, 0, tzinfo=MLB_TIMEZONE)

    target = next_run_at(now)

    assert target == dt.datetime(2026, 8, 18, 9, 0, tzinfo=MLB_TIMEZONE)


def test_next_run_rolls_to_tomorrow_when_after_the_run_time():
    now = dt.datetime(2026, 8, 18, 14, 0, tzinfo=MLB_TIMEZONE)

    target = next_run_at(now)

    assert target == dt.datetime(2026, 8, 19, 9, 0, tzinfo=MLB_TIMEZONE)


def test_next_run_rolls_to_tomorrow_at_the_exact_run_time():
    """Strictly after ``now`` — hitting the run time exactly shouldn't fire
    twice in a row.
    """
    now = dt.datetime(2026, 8, 18, 9, 0, tzinfo=MLB_TIMEZONE)

    target = next_run_at(now)

    assert target == dt.datetime(2026, 8, 19, 9, 0, tzinfo=MLB_TIMEZONE)


def test_next_run_converts_a_different_timezone_to_eastern():
    # 05:00 UTC is 01:00 US/Eastern (EDT, UTC-4) in August — well before 09:00.
    now = dt.datetime(2026, 8, 18, 5, 0, tzinfo=dt.timezone.utc)

    target = next_run_at(now)

    assert target == dt.datetime(2026, 8, 18, 9, 0, tzinfo=MLB_TIMEZONE)


def test_next_run_treats_a_naive_datetime_as_already_eastern():
    now = dt.datetime(2026, 8, 18, 6, 0)  # no tzinfo

    target = next_run_at(now)

    assert target == dt.datetime(2026, 8, 18, 9, 0, tzinfo=MLB_TIMEZONE)


def test_default_run_time_is_before_the_earliest_first_pitch():
    assert DEFAULT_RUN_TIME < dt.time(hour=11, minute=0)
