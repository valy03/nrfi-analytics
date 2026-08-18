"""M7 — unattended daily scheduling for the prediction job.

A minimal loop, not a cron reimplementation: compute the next occurrence of
the configured run time in US/Eastern (the same timezone
``app.collection.mlb_stats.mlb_today`` uses, so the scheduler and the job it
triggers always agree on what day "today" is), sleep until then, run the
job, repeat. Wired as its own docker-compose service (``scheduler``) rather
than a cron line inside the backend container, so it's visible alongside the
rest of the stack (``docker compose ps``) and its output is
``docker compose logs scheduler`` like everything else — this is the
concrete thing that makes the job actually unattended rather than something
a person has to remember to run.

Run time defaults to 09:00 US/Eastern — comfortably ahead of the earliest
regular-season first pitch (11:00 AM local, on getaway days) while still
late enough that most probable starters for the day are already announced.
A handful of TBD-starter games at run time simply don't get predicted that
day; ``app.prediction.job`` already skips them cleanly and there's no
same-day retry. Revisit if that turns out to lose meaningful coverage.

Run it:
    python -m app.prediction.scheduler
"""

from __future__ import annotations

import datetime as dt
import time as time_module

from app.collection.mlb_stats import MLB_TIMEZONE
from app.db.session import session_scope
from app.prediction.job import run

DEFAULT_RUN_TIME = dt.time(hour=9, minute=0)


def next_run_at(
    now: dt.datetime, run_time: dt.time = DEFAULT_RUN_TIME
) -> dt.datetime:
    """The next wall-clock moment ``run_time`` occurs in US/Eastern, strictly
    after ``now``. ``now`` may be naive (assumed already US/Eastern) or
    tz-aware in any zone.
    """
    now = now.astimezone(MLB_TIMEZONE) if now.tzinfo else now.replace(tzinfo=MLB_TIMEZONE)
    candidate = now.replace(
        hour=run_time.hour, minute=run_time.minute, second=0, microsecond=0
    )
    if candidate <= now:
        candidate += dt.timedelta(days=1)
    return candidate


def run_once() -> None:
    try:
        with session_scope() as session:
            result = run(session)
        print(
            f"[scheduler] {result['date']}: {result['predicted']} predicted "
            f"({result['eligible']} eligible, "
            f"{result['skipped_started']} already started, "
            f"{result['skipped_no_starters']} missing a starter)"
        )
    except Exception as exc:  # noqa: BLE001 - this loop must never die
        # The M7 "logging/alerting on job failure" deliverable: a bad run
        # gets logged and the loop tries again tomorrow instead of exiting
        # and silently going dark for the rest of the season.
        print(f"[scheduler] ERROR: prediction job failed: {exc}")


def main() -> None:
    print(f"[scheduler] started — daily run at {DEFAULT_RUN_TIME} US/Eastern")
    while True:
        target = next_run_at(dt.datetime.now(MLB_TIMEZONE))
        print(f"[scheduler] next run at {target.isoformat()}")
        time_module.sleep(max(0.0, (target - dt.datetime.now(MLB_TIMEZONE)).total_seconds()))
        run_once()


if __name__ == "__main__":
    main()
