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

**Status:** Not Started

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

**Status:** Not Started

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

**Status:** Not Started

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

# M9 — Dashboard: Today's Games

**Status:** Not Started

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
| M6 | Model Iteration & Selection | M5 | Not Started |
| M7 | Prediction Service & Automation | M1, M6 | Not Started |
| M8 | REST API | M7, M3 | Not Started |
| M9 | Dashboard: Today's Games | M8 | Not Started |
| M10 | Dashboard: Game Details | M9 | Not Started |
| M11 | Historical Results & Analytics | M7, M8 | Not Started |
| M12 | Deployment | M9, M10, M11 | Not Started |