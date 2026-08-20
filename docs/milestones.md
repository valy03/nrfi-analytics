# NRFI Analytics — milestones.md

> This document sequences the project into concrete, ordered milestones.
>
> It answers the question: "In what order do we build this, and how do we
> know each stage is actually done?"
>
> Each milestone has a goal, deliverables, and an exit criteria (Definition
> of Done). No milestone should start until the previous one's exit
> criteria are met — this mirrors the architecture in planning.md
> (Data Sources → Collection → DB → Features → Model → Service → API → UI).

---

# How to use this doc

- Work top to bottom. Resist building UI before the data pipeline is real —
  it's tempting but produces a pretty dashboard with fake numbers.
- Each milestone maps to a learning goal from planning.md, so the order is
  also a curriculum, not just a build sequence.
- Update status inline as you go: `Not Started / In Progress / Done`.
- If a milestone starts sprawling past its exit criteria, that's a sign to
  split it, not to keep building.

---

# M0 — Project Scaffolding

**Status:** Done (2026-07-27) — verified via `docker compose up`: DB
healthy, backend `/health` returning 200, frontend loading and
successfully calling the backend.

**Goal:** A skeleton repo exists and runs, with nothing real in it yet.

**Deliverables:**
- Repo structure (backend/, frontend/, data/ or etl/, docs/)
- FastAPI app that boots and returns a health check endpoint
- React app that boots and renders a placeholder page
- PostgreSQL running locally (Docker Compose)
- `.env` / config pattern for secrets (weather key, odds key)
- README with setup instructions

**Exit Criteria:**
- `docker compose up` (or equivalent) brings up DB + backend + frontend
- Backend health endpoint returns 200
- Frontend loads in browser and shows a placeholder

**Depends on:** research.md data source decisions (done)

---

# M1 — Data Collection: MLB Stats API (Operational)

**Status:** Done (2026-07-27) — `app.collection.mlb_stats` pulls the daily
schedule + probable pitchers via the MLB-StatsAPI wrapper. Verified against
today's slate (games with pitchers where announced, `TBD` otherwise) and a
past date (2024-04-10, returning `Final` statuses and scores). 9 mocked unit
tests pass.

**Goal:** Can reliably pull today's MLB schedule and confirmed starting
pitchers on demand.

**Deliverables:**
- Script/module that calls MLB Stats API for a given date
- Returns: games, home/away teams, venue, game time, starting pitchers
  (when announced)
- Basic error handling for days with no games / unannounced pitchers

**Exit Criteria:**
- Running the script for today's date returns a clean, structured list of
  today's games with pitchers where available
- Running it for a past date returns historical schedule/boxscore data

**Depends on:** M0

---

# M2 — Data Collection: Statcast Historical Backfill

**Status:** Done (2026-07-27) — `app.collection.statcast_backfill` pulls
Statcast pitch data (chunked by month, cached to parquet, with retry on
transient Savant connection drops), derives one NRFI-labeled row per game
chunk-by-chunk (bounded memory), and merges idempotently into
`data/processed/nrfi_games.parquet`. **Full 2018–2025 window backfilled:
17,906 games, 0 duplicates, 0 null labels, 50.2% NRFI** (per-season 47–53%,
2020 correctly 898 for the COVID year). Labels cross-checked 24/24 against the
MLB Stats API linescore across multiple seasons. 11 mocked unit tests pass.
Backfill is incremental/idempotent — re-running reuses cached chunks and never
duplicates games; top up with recent games by extending `--end`.

**Goal:** A local historical dataset of pitch-level data exists, from which
NRFI/YRFI outcomes can be derived for every game in the training window.

**Deliverables:**
- `pybaseball` integration to pull Statcast data for a defined date range
  (recommend starting 2018–present per research.md)
- A transformation step that collapses pitch-level rows into one row per
  game with a derived NRFI/YRFI label (first-inning runs scored, both
  halves)
- Raw data cached locally (parquet/CSV) so repeated backfills don't re-hit
  Baseball Savant unnecessarily

**Exit Criteria:**
- A dataset exists covering the full training window with one row per
  game and a correct NRFI/YRFI label, spot-checked against a few known
  games
- Backfill is re-runnable/idempotent (won't duplicate on re-run)

**Depends on:** M0

---

# M3 — Database Schema & Ingestion

**Status:** Done (2026-08-04) — seven tables (`teams`, `pitchers`, `games`,
`pitcher_game_stats`, `team_game_stats`, `predictions`,
`prediction_results`) defined as SQLAlchemy models and created via a single
Alembic migration that round-trips (`downgrade base` → `upgrade head`) with
`alembic check` reporting no model drift. **Full M2 backfill loaded: 17,906
games, 50.2% NRFI, 0 unlabeled** — matching the parquet exactly. Both loaders
are idempotent: a second run of either reports `0 inserted, 0 updated`.

`games` is deliberately shared by both sources on `game_pk`: the Statcast
loader writes the first-inning label, the daily loader writes
schedule/venue/pitchers, and the upsert never overwrites a stored value with
`None`, so neither erases the other. Verified on 2025-07-01, where 15
Statcast-labeled rows were enriched in place (`0 inserted, 15 updated`) with
labels intact. 20/20 stored Statcast labels cross-check against the MLB
linescore. 57 tests pass (28 new, offline against in-memory SQLite).

Two fixes surfaced along the way: probable-pitcher **ids** (needed as foreign
keys) aren't in the wrapper's schedule feed, so `fetch_schedule` grew an
opt-in hydrated lookup; and `date.today()` on a UTC host resolves to
*tomorrow's* slate late at night, so all "today" defaults now go through
`mlb_today()` (US Eastern) — which matters for the M7 scheduled job.

**Goal:** Historical and daily data lands in PostgreSQL, not just local
files.

**Deliverables:**
- Schema for: games, teams, pitchers, pitcher_game_stats,
  team_game_stats, predictions, prediction_results
- Migration tooling (Alembic or equivalent)
- Ingestion scripts that load the M1 (daily) and M2 (historical) data into
  the schema

**Exit Criteria:**
- Historical backfill from M2 is fully loaded into Postgres
- Running the M1 daily script inserts/updates today's games in Postgres
  without duplicating rows on re-run

**Depends on:** M1, M2

---

# M4 — Feature Engineering Pipeline

**Status:** Done (2026-08-05) — `app.features` turns stored data into a
32-feature matrix over 17,933 labeled games, **0 NaNs, 0 infinities, no
zero-variance columns**, built in ~3s.

M4 began with a collection step the deliverables didn't spell out: the
`pitcher_game_stats` / `team_game_stats` tables M3 defined were empty, and
`games` didn't record who started the 17,906 historical games.
`app.collection.statcast_boxscore` re-reads the cached Statcast chunks and
derives per-game first-inning lines (36,081 pitcher lines — 35,812 starters,
exactly two per game — and 35,812 team lines), which
`app.ingestion.game_stats` loads. Run attribution cross-checks **1,164 of
1,164 games** against the independently-derived M2 labels.

Features are as-of by construction: every aggregate is a backward
`merge_asof` with `allow_exact_matches=False`, so a game only ever sees
strictly earlier dates. That rules out same-day leakage (a doubleheader's
game 2 can't read game 1 — legal in hindsight, unavailable at 9am when the
M7 job runs) and makes training and inference literally the same call.

Cold starts are handled by empirical-Bayes shrinkage with **measured**
constants (`app.features.shrinkage`), not guessed ones. The first pass used a
hand-picked k=12 for pitchers and produced a feature spanning 0.61–0.80
against an outcome spanning only 0.69–0.76 — three times over-dispersed.
Decomposing observed spread into talent plus sampling noise gives k=182;
recalibrated, the feature spans 0.058 against an outcome spread of 0.073 and
the deciles are monotonic. The same estimator returns k=86 batters faced for
first-inning K%, independently reproducing the known ~70 PA stabilization
point for strikeout rate.

Verified: deleting 2.5 years of future data and rebuilding changes **nothing**
(max abs diff 0.0 across 32 features × 10 games); a slate of unplayed games
gets full feature rows with a null target; per-season NRFI reconciles exactly
with M2/M3. 17 feature tests, 74 total, all offline.

**Known limitation:** OPS/OBP/SLG are not implemented. They need
plate-appearance classification from Statcast `events`, and first-inning-only
slash lines are thin samples; first-inning scoring rate and runs/game carry
most of the same signal for less machinery. Revisit in M6 if feature
importance says recency and rate stats matter. Pitcher ERA is deliberately
replaced by runs allowed — Statcast doesn't mark earned/unearned, and the
NRFI label counts unearned runs anyway, so runs allowed is better aligned.

**Goal:** A reproducible pipeline turns raw stored data into a feature
matrix ready for model training.

**Deliverables:**
- Feature computation for: pitcher first-inning ERA/WHIP/K%/BB%/career &
  season NRFI%, team first-inning scoring %/OPS/OBP/SLG, home/away splits
- A single function/script: given a date (or game_id), returns the feature
  row(s) for that game — usable both for training (historical) and
  inference (today's games)
- Features stored or cached in a way that avoids recomputation on every
  prediction

**Exit Criteria:**
- Feature matrix can be generated for the full historical dataset with no
  missing/NaN blowups
- The same function produces a sane feature row for a game that hasn't
  happened yet (using only pre-game data — no leakage)

**Depends on:** M3

---

# M5 — Baseline ML Model

**Status:** Done (2026-08-17) — `app.training` trains a scaled Logistic
Regression on the M4 feature matrix and evaluates it against two naive
references. Run it with `python -m app.training.baseline`.

The split is by **season**, not randomly: train on 2018-2023 (n=13,047),
test on 2024-2026 (n=4,886, including the 27-game 2026 stub currently in the
database). A random split would let the model train on some 2025 games and
get evaluated on others — silently leaking roster/era information the model
will never have in production, where it only ever predicts a season it
hasn't seen. This is a different concern from the M4 as-of leakage guarantee
(that rules out same-game/future-date leakage no matter how the matrix is
sliced); this is about measuring forward generalization honestly.

Two references, each fit on the training set only:

| | Accuracy | ROC AUC | Log loss |
|---|---|---|---|
| Logistic Regression | **0.519** | **0.515** | 0.6948 |
| Majority-class (always predict training's more common label) | 0.484 | 0.500 | 17.81 |
| League-average rate (always predict training's NRFI rate) | 0.484 | 0.500 | 0.6934 |

The model beats the majority-class reference on accuracy and ranks games
better than chance (AUC > 0.5) — both gating criteria in
`app.training.baseline.passed`. It does *not* beat the league-average
reference on log loss, and that's reported rather than hidden or gated on:
log loss rewards calibration and discrimination together, and M4 already
established that first-inning pitcher talent has a standard deviation of
just 0.034 against a 0.712 mean — most of the spread is sampling noise, not
skill. With AUC this close to 0.5, the log-loss improvement a real but weak
edge should produce is the same order of magnitude as noise over ~4,900 held-
out games, so a model can rank better than chance and still land within
noise of the constant baseline on log loss. That isn't evidence of no
signal, just of a small one — which is the honest state of a first-inning
market before adding weather, bullpen, or park-specific features (M6+).

The majority-class reference's log loss (17.81) looks absurd by design: it
asserts 100% certainty in one label, so every miss costs almost nothing in
accuracy but catastrophically in log loss. That's exactly why log loss is
graded against the league-average reference instead — a fair calibration
floor — while accuracy is graded against the majority-class reference — a
fair discrimination floor. Grading both against the same reference would
have been the wrong comparison for one of the two.

Artifacts (`data/models/m5-v1.joblib`, `data/models/m5-v1_metrics.json`) are
gitignored per M6's existing `*.joblib` rule — regenerate with the command
above rather than expecting them in the checkout. 12 new offline tests
(synthetic data, no database), 86 total.

**Goal:** A working, interpretable baseline model exists and is honestly
evaluated.

**Deliverables:**
- Train/test split (time-based, not random — no future leakage)
- Logistic Regression baseline trained on M4 features
- Evaluation report: accuracy, precision, recall, F1, ROC AUC, log loss
- Baseline compared against a "dumb" reference (e.g. always predict
  majority class, or league-average NRFI rate) to confirm the model adds
  signal

**Exit Criteria:**
- Baseline model beats the naive reference on held-out data
- Evaluation metrics are written down (this becomes the bar M6 has to
  clear)

**Depends on:** M4

---

# M6 — Model Iteration & Selection

**Status:** Done (2026-08-17) — `app.training.compare` trains an XGBoost
candidate alongside the M5 Logistic Regression on the identical season split
(2018-2023 train, 2024-2026 test), scores both through the same
`app.training.report` path, and picks a champion. Run it with
`python -m app.training.compare`.

|  | Accuracy | ROC AUC | Log loss |
|---|---|---|---|
| Logistic Regression (M5) | 0.519 | **0.515** | 0.6948 |
| XGBoost (M6 candidate) | 0.505 | 0.506 | 0.6932 |

**XGBoost loses, and stays unselected.** Its AUC (0.506) is actually *below*
the Logistic Regression baseline's (0.515) on the held-out set, even though
it edges ahead on log loss. That's the expected result for this feature set,
not a bug: M4 already established that first-inning talent has a standard
deviation of just 0.034 against a 0.712 mean, so almost all of the spread
between pitchers is noise, not skill. Gradient-boosted trees earn their
keep by capturing nonlinear interactions real structure creates — with a
target this close to a coin flip, the extra flexibility mostly fits noise in
the training seasons instead, which is exactly what shows up as the AUC
inversion between train-side flexibility and test-side generalization. XGBoost's
own feature-importance ranking (`home_sp_k_rate_1st`, `away_sp_runs_1st_avg`,
`away_sp_k_rate_1st`) largely echoes the Logistic Regression's, so the two
models agree on *which* stats matter — pitcher first-inning rate stats
dominate both — they just disagree on how to combine them, and the simpler
combination generalizes better here.

Both candidates individually clear the M5 gating bar (beat the majority-class
reference on accuracy, rank better than chance on AUC); `select_champion`
picks by held-out ROC AUC among whichever candidates pass that gate, so a
higher-AUC model that *failed* the gate would still lose to a passing one —
exercised directly in `tests/test_compare.py`. The Logistic Regression wins
on both counts, so it remains the champion.

Champion selection is a generic, model-agnostic function (`build_candidates`
returns a list, not a hardcoded pair), so a future LightGBM or Random Forest
candidate slots in the same way — deliberately not built now since the
result above suggests more model complexity isn't this dataset's bottleneck;
better features (bullpen, weather, park-specific effects — flagged as future
work in M4) are a more promising lever than a fancier estimator.

Artifacts land in `data/models/` (gitignored): `champion.joblib` /
`champion_metrics.json` are what M7 will load for inference — model-name-
agnostic, so the inference path doesn't need to know which family won.
`m6-xgb-v1.joblib` / `m6-xgb-v1_metrics.json` are the standalone XGBoost
run, and `m6_comparison.json` holds the full head-to-head with both models'
feature importances. 9 new offline tests (synthetic data, no database), 95
total.

**Goal:** A stronger model is chosen deliberately, not just swapped in.

**Deliverables:**
- XGBoost (and optionally LightGBM/Random Forest) trained on the same
  features/split as M5
- Head-to-head comparison against the M5 baseline on the same held-out set
- Basic feature importance review (which features actually matter — this
  is also how the "which stats are predictive?" research question gets
  answered)
- Model version + artifact saved (not retrained per request, per
  requirements.md)

**Exit Criteria:**
- A model is selected with justification (metrics + feature importance),
  not just "XGBoost is fancier"
- Model artifact can be loaded and used for inference without retraining

**Depends on:** M5

---

# M7 — Prediction Service & Daily Automation

**Status:** In Progress (started 2026-08-17) — everything is built and
verified against real, live data. The only remaining exit criterion (running
*unattended* across a few real game days) is deliberately deferred to M12,
rather than chased on a laptop that would have to stay awake for days to
prove it — see "Decision" below. Predictions keep flowing via manual job
runs in the meantime.

`app/prediction/` ties M1 → M3 → M4 → M6 together:
- `infer.py` loads whatever `app.training.compare` most recently selected as
  champion (`data/models/champion.joblib` + its metadata) and scores a
  feature matrix into prediction payloads — label, both probabilities,
  confidence (distance from a coin flip, rescaled 0-1), and a snapshot of
  the exact feature values used, so an old prediction stays explainable
  after the feature pipeline moves on.
- `store.py` upserts into `predictions`, keyed on `(game_pk, model_version)`
  — a re-run updates a slate's predictions in place, and a new champion
  version adds new rows alongside the old ones instead of overwriting
  history (what M11's model-version comparison will need).
- `job.py` (`python -m app.prediction.job [--date ...]`) is the orchestrator:
  refresh the day's schedule via the M1/M3 `app.ingestion.daily.load_date`,
  narrow to games that are actually safe to predict, compute features for
  just those games, run inference, store. "Safe to predict" is an allowlist
  of pre-game statuses (`Scheduled`, `Pre-Game`, `Warmup`, ...) — not a
  blocklist — plus both starters announced, so an MLB status string the job
  doesn't recognize defaults to *skip*, and the application never predicts a
  live or finished game (requirements.md). Skips are counted and printed,
  not silently dropped.
- `scheduler.py` (`python -m app.prediction.scheduler`) is the "no manual
  intervention" half: a small loop that sleeps until 09:00 US/Eastern (the
  same timezone `mlb_today()` uses, so the two always agree on what day
  "today" is — comfortably ahead of the 11:00 AM earliest getaway-day first
  pitch, late enough that most starters are announced by then), runs the
  job, logs the result, and repeats. Wired as its own `scheduler` service in
  `docker-compose.yml` (`restart: unless-stopped`) rather than a cron line
  inside the backend container, so it shows up in `docker compose ps` and
  its output is `docker compose logs scheduler` like everything else. A
  failed run is caught, logged, and the loop tries again the next day
  instead of dying — the M7 "logging/alerting" deliverable.

**A real bug this surfaced:** running the job against real data (tomorrow's
actual slate, 2026-08-18: 15 games, 3 with a TBD starter) crashed
`compute_features` — `IntCastingNaNError` on the as-of join. M4's tests only
ever exercised games with a concrete starting pitcher on both sides, so the
NULL-until-announced case (the normal state of a few games on any real
slate) was untested and broken. Fixed in `app/features/compute.py`'s
`_as_of`: an entity key that's missing gets remapped to a sentinel that
can't match any real id (real MLB ids are always positive), so it comes
back with zero prior appearances — the same league-average fallback a
debut pitcher already gets — instead of crashing the dtype cast. Regression
test added to `test_features.py`. This is exactly why "run it against real
data" is part of the exit criteria and not just "the tests pass": the
synthetic M4 test fixtures never had a reason to omit a starter.

Verified end to end against the live MLB Stats API for 2026-08-18: eligible
12, skipped 0 already-started, skipped 3 missing a starter, 12 predicted and
stored in Postgres with the correct champion model/version attached
(`logistic_regression_baseline` / `m5-v1`). Re-running reported
`0 inserted, 0 updated, 12 unchanged` — idempotent, as designed.

**Decision (2026-08-17): deferring the "observed unattended" check to M12,
not chasing it locally.** The scheduler works — verified it boots, computes
the correct next-fire time, and would have fired at 09:00 ET the next
morning — but "unattended for a few real game days" on a laptop actually
means "Docker Desktop, and the machine under it, staying awake continuously
for days," which isn't a cost worth paying just to check a box early. That's
solving the problem in the wrong place: a scheduled job that only survives
while someone's laptop is open isn't meaningfully unattended anyway. The
`scheduler` container is implemented, tested (`next_run_at` in
`test_scheduler.py`), and wired into `docker-compose.yml` — it's stopped for
now, not removed. Real unattended verification happens once M12 puts this on
Railway, where "unattended" actually means something.

In the meantime, predictions keep landing via manual runs of the same job
the scheduler would call —

    docker compose exec backend python -m app.prediction.job

— which exercises every part of M7 except the timer. M7 stays **In
Progress**; it moves to Done alongside (or right after) M12, once the
scheduled version has actually been observed running without anyone
watching it.

**Goal:** Predictions generate automatically every day with no manual
steps, per requirements.md.

**Deliverables:**
- Scheduled job (cron / Railway scheduled job) that: pulls today's
  schedule (M1) → computes features (M4) → runs inference (M6 model) →
  stores prediction + confidence + model version + timestamp (M3 schema)
- Job runs early enough to beat the first scheduled game
  (performance requirement from requirements.md)
- Logging/alerting on job failure (even just a log line — doesn't need to
  be fancy for MVP)

**Exit Criteria:**
- Job has run successfully, unattended, for at least a few consecutive
  real game days, with predictions landing in Postgres before first pitch

**Depends on:** M1, M6

---

# M8 — REST API

**Status:** Done (2026-08-18) — eight endpoints across three routers
(`app/routers/games.py`, `history.py`, `analytics.py`), all wired into
`main.py` under `/api`, all verified against live production data (17,933+
historical games, real predictions from a real MLB slate) — not just the
offline test suite.

**Scope decision going in:** M8's exit criteria calls for "every MVP
dashboard feature... backed by real stored data (not mocks)," but three
categories of requirements.md field have no data source at all — no prior
milestone ever built them: weather (OpenWeather, decided in research.md but
never collected), betting odds (The Odds API, same gap), and traditional
pitcher/team stats (ERA, WHIP, FIP, xERA, OPS, OBP, SLG, batting average —
M4 deliberately computed first-inning-only versions for the model and
explicitly skipped these as display stats). Rather than block M8 on new
external API integrations, or silently fabricate placeholder values, the
decision (asked of and confirmed by the user) was: ship the core API now on
real data, with those specific fields present in the response schemas and
explicitly typed nullable, returning `null` today. The contract is ready;
the data is a documented fast-follow, not invented.

**Two gaps M8 surfaced that belonged to no prior milestone:**

1. **Grading.** Nothing connected a stored prediction to the game's
   now-known outcome — M7 predicts before the game, M1/M3's daily loader
   labels the outcome after, and nothing joined the two. Added
   `app/grading/results.py`: for every prediction whose game now has a
   known result and no `PredictionResult` yet, write one (`actual_label`,
   `correct`; `odds_american`/`stake`/`profit` stay null, no odds source).
   Idempotent — already-graded predictions are skipped via the "no result
   yet" check, so a daily re-run only picks up newly-finished games. This
   is why `/api/history/accuracy` and `/api/analytics/models` can be
   honest: they only count *graded* predictions, so an in-flight one isn't
   silently scored as a win or a loss.

2. **A real M4 bug.** Not new to M8, but this is where it was caught:
   `compute_features` crashed (`IntCastingNaNError`) on a game with an
   unannounced starting pitcher — the normal state of a few games on any
   real slate, but untested because every M4 synthetic fixture always
   supplied concrete pitcher ids. Fixed in `app/features/compute.py`
   (`_as_of`: a missing entity key now maps to a sentinel no real id can
   match, falling back to the league average exactly like a debut pitcher,
   instead of crashing the dtype cast). Regression test in
   `test_features.py`. Recorded here rather than reopening M4/M7's status.

**What each router serves:**

- **`games.py`** — `GET /api/games` (today's slate by default, or `?date=`;
  filters `prediction=NRFI|YRFI`, `min_confidence`, `team` substring
  search; `sort_by=confidence`) and `GET /api/games/{game_pk}` (full
  detail: teams, pitchers, team stats, prediction, explanation, actual
  result once played). Pitcher/team rate stats and the explanation are
  sourced from the *stored prediction's feature snapshot*
  (`Prediction.features`), not recomputed live — a game's displayed
  numbers are exactly what the model saw, and a game with no prediction
  (no announced starters, or predates M7) honestly shows no rate stats
  rather than a live recomputation that could drift from what was
  predicted. "Last 5 starts" is real per-start data queried from
  `pitcher_game_stats`, not an aggregate.
- **`history.py`** — `GET /api/history/predictions` (past predictions with
  graded outcome where available, filterable by date range/team/model
  version, paginated) and `GET /api/history/accuracy` (overall/yearly/
  monthly accuracy — `win_rate` is the same number as `accuracy` for a
  binary market bet straight every time, exposed under both names because
  requirements.md lists them separately; `roi` stays null, no odds).
- **`analytics.py`** — `GET /api/analytics/nrfi-frequency` (by season, from
  the full 2018-2026 history — dense from day one, unlike accuracy which
  only fills in as M7 keeps running), `/pitchers` and `/teams`
  leaderboards (first-inning NRFI rate, with a minimum-appearances floor
  so one clean start can't outrank a real season), and `/models`
  (graded accuracy per model_name/model_version — the concrete payoff of
  M6's multi-version design).

**Explanation generation** (`app/queries/explain.py`) compares each side
head-to-head (home starter's NRFI rate vs. away's, home offense's
first-inning rate vs. away's, this park's rate vs. a plainly-labeled 50%
coin flip) rather than against a hardcoded "league average": every feature
is already shrunk toward whatever the *as-of* league rate was on the day of
that specific game (M4), so there's no single constant to compare against
without re-guessing a number M4 went to real effort to stop guessing. The
top 3 factors by magnitude of divergence get rendered as plain sentences.
Not SHAP — that's still a stretch goal.

**Known gap, not yet worth solving:** `predictions` currently only has rows
for the one real slate M7 has predicted so far — there's no history to
show on `/api/history/*` or `/api/analytics/models` until M7 (or manual
runs) accumulate more real days. Backfilling predictions retroactively over
the 2018-2025 training-era games was considered and rejected for now: the
champion model was trained on exactly that data, so "predicting" it after
the fact would be look-ahead bias dressed up as a track record, not a
real one.

61 new offline tests (synthetic data + in-memory SQLite via a new `client`
TestClient fixture in `conftest.py`), 175 total. Verified live against
Postgres: all 8 endpoints, `/docs` Swagger UI, and the full OpenAPI spec.

**Goal:** Backend endpoints exist to serve everything the dashboard needs.

**Deliverables:**
- Endpoints: today's games + predictions, single game detail (pitchers,
  stats, weather, odds, explanation), historical results + accuracy
  stats, analytics/leaderboard data
- Explanation generation (rule-based summary of top contributing factors —
  doesn't need to be SHAP yet, that's a stretch goal)
- Basic sorting/filtering support (by confidence, prediction type) per
  requirements.md

**Exit Criteria:**
- Every MVP dashboard feature in requirements.md has a working endpoint,
  testable via Swagger/Postman, backed by real stored data (not mocks)

**Depends on:** M7 (need real predictions to serve), M3

---

# M8.5 — Weather & Odds Collection

**Status:** Done (2026-08-19) — both sources land in Postgres and surface
through the real `/api/games` endpoints, verified against live API calls
(not fixtures) for a real 9-game slate (2026-08-20).

**Venue coordinates came from the MLB Stats API itself, not a hand-typed
table.** The deliverable left "static table if [venue data] is thin" as a
fallback, but `statsapi.get('venue', {'venueIds': ..., 'hydrate': 'location'})`
returns real `defaultCoordinates` (lat/lon) for every park directly — including
current details for parks that wouldn't be in any static list written from
memory (the Athletics' temporary home at Sutter Health Park, renamed venues
like Daikin Park and Rate Field). `app/ingestion/venues.py` seeds a `venues`
reference table the same way `app/ingestion/teams.py` seeds `teams` — not
foreign-keyed from `games.venue_id`, deliberately: the M2 historical backfill
includes spring-training and international venues outside the ~30 active
parks, and a hard FK against ~18k already-loaded games risked failing on
exactly the rows this table was never meant to cover. It's a lookup
`app.collection.weather` resolves what it can from, not a constraint.

**A real bug, caught before it shipped:** `Venue.latitude`/`longitude` and
`Game.weather_temp_f`/`weather_wind_mph` were first modeled as `Numeric` —
matching decimal-money-style columns elsewhere in the schema. Postgres (and
SQLite) read a `Numeric` column back as `decimal.Decimal`, and comparing that
against the plain `float` the APIs return is `app.ingestion.upsert`'s
change-detection check — `Decimal('42.346456') != 42.346456` is `True` more
often than not, because a float's nearest binary value rarely matches a
Decimal's exact one. Every re-seed would have reported "updated" forever,
never "unchanged" — the exact idempotency guarantee every M1-M8 loader is
built around. Caught by `test_seed_venues_is_idempotent` actually failing
during development, not by inspection. Fixed by using `Float` for anything
that's a measurement, not a database Decimal for anything that isn't money.

**Weather** (`app/collection/weather.py`, OpenWeather free tier): the free
tier has no point-in-time-in-the-future forecast, so a game's conditions are
the closest 3-hour forecast bucket to its actual start time
(`/data/2.5/forecast`), not a live "right now" reading — the two can differ
by up to ~90 minutes when the job runs well before first pitch, an accepted
approximation for a display-only field. `app.prediction.enrich` fetches the
forecast once per *unique venue* among a slate's eligible games and picks
each game its own closest bucket from that one response, so a doubleheader
never costs two calls.

**Odds** (`app/collection/odds.py`, The Odds API free tier): one request
returns the *entire* day's MLB slate with every bookmaker's moneyline, so
"one call per day" was already the natural shape — no batching logic needed,
just not calling it more than once. (The free tier is actually a 500-request
quota, not the 25/day `research.md` recorded — corrected there. Doesn't
change anything: the design was already one call regardless.) DraftKings is
preferred when present, falling back to whatever bookmaker posted a line.

Both are wired into `app/prediction/job.py` right after predictions save,
and both are deliberately **best-effort**: `enrich_weather`/`enrich_odds`
catch their own API errors and simply write nothing for that run rather than
raising — a weather outage must never fail the job predictions actually
depend on. Verified live: `python -m app.prediction.job --date 2026-08-20`
against a real 9-game slate captured real temps (69.9-102.7°F), conditions
(Clear/Rain/Clouds), and DraftKings moneylines for all 9 games; re-running
correctly refreshed all 9 (weather/odds are point-in-time snapshots, not
static reference data, so every run *should* report "updated," not
"unchanged" — confirmed via `docker compose logs` and a direct
`/api/games/822934` request showing the real captured values). The Odds API
quota showed 495/500 remaining after this session's testing.

`app/schemas/games.py`'s `weather`/`odds` fields — `dict[str, Any]`
placeholders since M8 — are now typed `WeatherOut`/`OddsOut` models. 41 new
tests (venue seeding, both API clients with `requests` stubbed, enrichment
against the SQLite fixture, the API layer with real captured values), 212
total.

**Goal:** The two data sources `research.md` decided on but no milestone
ever actually collected — weather (OpenWeather) and betting odds (The Odds
API) — land in Postgres, so M8's `weather`/`odds` response fields stop
being permanently `null`.

Inserted here rather than folded into M9/M10: both are Collection-layer
concerns in `planning.md`'s own architecture (Data Sources → Collection →
DB → Features → Model → Service → API → UI) — the same category as M1
(schedule) and M2 (Statcast), not dashboard work. Building them inside a
milestone titled "Dashboard" would mix an external-API-client-and-migration
task into what should be frontend work. No renumbering of M9-M12 needed;
this just reads between M8 and M9.

**Deliverables:**
- A venue → lat/lon lookup for the 30 parks (MLB Stats API's venue data, or
  a static table if that's thin) — OpenWeather needs coordinates, not city
  names, to be accurate
- `app/collection/weather.py`: OpenWeather free-tier client, current
  conditions near first pitch for a given venue/time
- `app/collection/odds.py`: The Odds API free-tier client, MLB moneyline
  only, matched to today's games by team + date. Display-only per
  `research.md` — not a model input, so no feature-pipeline or training
  changes
- Schema: nullable `weather`/`odds` columns or a small side table (open
  question — a table if either source might carry multiple readings per
  game, e.g. odds line movement; a column if it's always "latest snapshot
  only," which matches `research.md`'s "display-only" decision)
- Wire both into the M7 job (or a step alongside it) so they're captured
  once per day, same cadence as predictions
- M8's `games_for_date` / `game_detail` queries populate the `weather`/
  `odds` response fields instead of hardcoding `None`

**Exit Criteria:**
- A real game's `/api/games/{game_pk}` response shows real weather and
  real odds, sourced from live API calls, not fixtures
- Free-tier rate limits are respected — The Odds API in particular needs
  the whole day's slate covered by very few calls, not one call per game

**Depends on:** M7 (shares its daily cadence), M8 (defines the response
shape these fields fill in)

---

# M9 — Dashboard: Today's Games

**Status:** Done (2026-08-19) — the homepage fetches `/api/games` (no
`date` param, so the backend resolves "today" via `mlb_today()` rather than
trusting the visitor's browser timezone) and renders every field
requirements.md asks for. `tsc -b` and `vite build` both pass clean, and
the rendered page was actually eyeballed in a browser and confirmed good —
this session has no browser-automation tool, so a human did that check
directly rather than it being claimed on the strength of a clean build.

**Two real bugs surfaced during that check, not by inspection:**

1. **Finished/in-progress games looked identical to "not predicted yet."**
   The first real screenshot showed today's slate almost entirely reading
   "No prediction yet" — correct in substance (M7 only predicts games that
   haven't started, and it was evening ET with 14 of 15 games already
   `Final`/`In Progress`), but misleading in presentation: nothing
   distinguished "this game already happened" from "check back later."
   `PredictionBadge` now mirrors `app/prediction/job.py`'s
   `PENDING_STATUSES` set client-side and shows the real status (`Final`,
   `In Progress`, ...) instead of the generic message once a game has
   actually started.

2. **The dev server was silently serving stale code.** Docker Desktop's
   Windows bind mount doesn't reliably forward filesystem events into the
   Linux container, so Vite's file watcher never fired — not just over the
   HMR websocket, but for fresh HTTP requests too, since Vite trusts its
   watcher to invalidate its transform cache rather than re-checking the
   file on every request. Confirmed directly: edited a component, `curl`'d
   its dev-server-transformed source, and the edit simply wasn't there,
   repeatedly, until the container was recreated with polling enabled.
   Fixed two ways — `server.watch.usePolling` in `vite.config.ts`, and the
   `CHOKIDAR_USEPOLLING`/`CHOKIDAR_INTERVAL` env vars on the `frontend`
   service in `docker-compose.yml`, since the config option alone wasn't
   enough and needed a full container recreate (not just `docker compose
   restart`) to take effect. Verified by editing a file and watching a real
   `hmr update` log line appear. Worth remembering for M10/M11: a
   no-op-looking UI change during this project might mean the dev server
   is stale, not that the change was wrong.

Team logos use MLB's own static CDN (`mlbstatic.com/team-logos/{team_id}.svg`,
keyed by the same id our API already returns) rather than a fabricated or
hand-picked source — confirmed live (200, `image/svg+xml`) for real team
ids before wiring it in, with a graceful text-abbreviation fallback if an
image ever 404s.

Sort/search/filter are **client-side**, not query params against M8's API,
even though the backend already supports all four server-side. A day's
slate is at most ~15 games — fetched once, filtered/sorted with plain
array methods in the browser. Instant on every keystroke, no debounce, no
loading spinner per filter change, and still fully satisfies
requirements.md's "sort by confidence / search teams / filter by
prediction / filter by confidence" — those are UI behaviors, not a mandate
for round-tripping to the server on every interaction.

`frontend/src/api/types.ts` mirrors `app/schemas/games.py` by hand — no
shared schema generation yet, so the two need to be kept in sync manually
if either changes.

**Goal:** The homepage described in requirements.md is real and wired to
the API.

**Deliverables:**
- Today's games list: teams, logos, pitchers, prediction, confidence,
  weather summary
- Sort by confidence, search teams, filter by prediction/confidence

**Exit Criteria:**
- Loads real data from M8 API, no hardcoded/mock data left in the frontend
- Loads in under 2 seconds per requirements.md

**Depends on:** M8

---

# M10 — Dashboard: Game Details

**Status:** Not Started

**Goal:** Clicking into a game shows the full breakdown.

**Deliverables:**
- Pitcher stats, team stats, historical matchups, weather, odds,
  prediction probabilities, explanation section

**Exit Criteria:**
- Every field listed under "Game Details" in requirements.md is present
  and populated from real data

**Depends on:** M9

---

# M11 — Historical Results & Analytics

**Status:** Not Started

**Goal:** Model accountability is visible — past predictions vs. actual
outcomes, and analytics charts.

**Deliverables:**
- Historical results table (prediction, actual, confidence, win/loss,
  date)
- Accuracy stats (overall/monthly/yearly, win rate, ROI)
- Charts: accuracy over time, NRFI frequency, pitcher/team leaderboards

**Exit Criteria:**
- Numbers shown reconcile with what's actually stored in the predictions/
  results tables (no fudged aggregates)

**Depends on:** M7, M8

---

# M12 — Deployment

**Status:** Not Started

**Goal:** The application is live and self-sustaining, per the MVP success
criteria in planning.md.

**Deliverables:**
- Backend + DB deployed (Railway)
- Frontend deployed (Vercel)
- Scheduled job running in production, not just locally
- Environment secrets configured in production

**Exit Criteria:**
- All six MVP success criteria from planning.md are met in the deployed
  environment:
  daily games update automatically / predictions generate automatically /
  users can view today's predictions / historical predictions are stored /
  dashboard displays analytics / application is deployed

**Depends on:** M9, M10, M11

---

# Stretch Milestones (post-MVP)

Not sequenced yet — pull from planning.md's Stretch Features list once MVP
(M0–M12) is done. Candidates in rough priority order:

1. Mobile responsive polish
2. SHAP-based explanations (upgrade from rule-based M8 explanations)
3. Model comparison view (multiple models side by side)
4. User accounts + favorite teams
5. Email alerts
6. AI chat assistant

---

# Milestone Summary Table

| # | Milestone | Depends On | Status |
|---|-----------|------------|--------|
| M0 | Project Scaffolding | — | Done |
| M1 | MLB Stats API Collection | M0 | Done |
| M2 | Statcast Historical Backfill | M0 | Done |
| M3 | Database Schema & Ingestion | M1, M2 | Done |
| M4 | Feature Engineering Pipeline | M3 | Done |
| M5 | Baseline ML Model | M4 | Done |
| M6 | Model Iteration & Selection | M5 | Done |
| M7 | Prediction Service & Automation | M1, M6 | In Progress |
| M8 | REST API | M7, M3 | Done |
| M8.5 | Weather & Odds Collection | M7, M8 | Done |
| M9 | Dashboard: Today's Games | M8 | Done |
| M10 | Dashboard: Game Details | M9 | Not Started |
| M11 | Historical Results & Analytics | M7, M8 | Not Started |
| M12 | Deployment | M9, M10, M11 | Not Started |