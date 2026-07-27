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

**Status:** Not Started

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

**Status:** Not Started

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

**Status:** Not Started

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

**Status:** Not Started

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

**Status:** Not Started

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
| M1 | MLB Stats API Collection | M0 | Not Started |
| M2 | Statcast Historical Backfill | M0 | Not Started |
| M3 | Database Schema & Ingestion | M1, M2 | Not Started |
| M4 | Feature Engineering Pipeline | M3 | Not Started |
| M5 | Baseline ML Model | M4 | Not Started |
| M6 | Model Iteration & Selection | M5 | Not Started |
| M7 | Prediction Service & Automation | M1, M6 | Not Started |
| M8 | REST API | M7, M3 | Not Started |
| M9 | Dashboard: Today's Games | M8 | Not Started |
| M10 | Dashboard: Game Details | M9 | Not Started |
| M11 | Historical Results & Analytics | M7, M8 | Not Started |
| M12 | Deployment | M9, M10, M11 | Not Started |