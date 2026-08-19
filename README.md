# NRFI Analytics

Transparent, data-driven No Run First Inning (NRFI) predictions for every
MLB game — explaining *why* a prediction was made, not just displaying a
confidence score.

See `docs/` for the full planning trail: `planning.md`, `requirements.md`,
`research.md`, `milestones.md`, `wireframes.md`. This README only covers
running what exists right now.

---

## Status

**M8.5 — Weather & Odds Collection (done).** On top of the M0 scaffolding,
the backend can pull the daily MLB schedule and probable starting pitchers
(M1), backfill historical Statcast pitch data into a per-game NRFI-labeled
dataset (M2), load both into PostgreSQL behind Alembic migrations (M3), turn
the stored data into a leakage-free 32-feature matrix over 17,933 games
(M4), train a season-split Logistic Regression baseline (M5), head-to-head
it against an XGBoost candidate that loses on held-out AUC so the simpler
model stays champion (M6), generate + store real predictions for the
champion model on demand, with an optional scheduler that automates the
timing (M7), serve all of it — today's games, game detail with a rule-based
explanation, historical accuracy, and analytics leaderboards — over a REST
API verified against live Postgres data (M8), and fill in that API's
weather/odds fields with real live-captured data instead of permanent
`null`s (M8.5). M7's own exit criterion (observed running *unattended*
across real game days) is still deferred to M12's real deployment — see
`docs/milestones.md`.

---

## Prerequisites

- Docker + Docker Compose
- (Only if running outside Docker) Python 3.12 and Node 22

---

## Quickstart

```bash
cp .env.example .env   # already done if you're reading this from the scaffold
docker compose up --build
```

Then:

- Frontend: http://localhost:5173 — should show "API reachable" once the
  backend responds.
- Backend health check: http://localhost:8000/health
- Backend interactive docs: http://localhost:8000/docs
- Postgres: `localhost:5432` (user `nrfi`, password `nrfi`, db
  `nrfi_analytics`)

## M0 Exit Criteria (from milestones.md)

- [x] `docker compose up` brings up DB + backend + frontend
- [x] Backend health endpoint returns 200
- [x] Frontend loads in browser and shows a placeholder that confirms API
      connectivity

Once you've confirmed all three locally, M0 is done — move on to M1
(MLB Stats API collection) and M2 (Statcast historical backfill) in
`docs/milestones.md`. Those can be worked in parallel.

---

## Data collection (M1)

Pull the schedule + probable pitchers for a date (runs inside the backend
container, which has the MLB-StatsAPI dependency):

```bash
docker compose exec backend python -m app.collection.mlb_stats                 # today
docker compose exec backend python -m app.collection.mlb_stats --date 2024-04-10
docker compose exec backend python -m app.collection.mlb_stats --date 2024-04-10 --json
```

Probable pitchers show as `TBD` until MLB announces them. Past dates return
final statuses and scores.

### Historical Statcast backfill (M2)

Pull pitch-level Statcast data and derive one NRFI-labeled row per game into
`data/processed/nrfi_games.parquet`:

```bash
# A small window (fast — good for a sanity check):
docker compose exec backend python -m app.collection.statcast_backfill --start 2023-04-01 --end 2023-04-07

# The full training window (LONG download, multi-GB — run when ready):
docker compose exec backend python -m app.collection.statcast_backfill --start 2018-01-01 --end 2025-12-31
```

Raw pulls are chunked by month and cached to `data/raw/statcast/`, so a
re-run reuses the cache instead of re-hitting Baseball Savant, and merges are
deduped by `game_pk` (safe to re-run). Regular season only by default; add
`--include-postseason` to keep spring/postseason games, or `--force` to
re-download cached chunks. The `data/` directory is gitignored.

## Database (M3)

The schema lives in `backend/app/models/` and is applied with Alembic.

```bash
# Create/upgrade the schema (safe to re-run)
docker compose exec backend alembic upgrade head

# After changing a model, generate a migration and review it before applying
docker compose exec backend alembic revision --autogenerate -m "what changed"
docker compose exec backend alembic check      # fails if models drift from the DB
docker compose exec backend alembic downgrade -1
```

Seven tables: `teams`, `pitchers`, `games`, `pitcher_game_stats`,
`team_game_stats`, `predictions`, `prediction_results`. `games` is the spine
— keyed on `game_pk`, which both data sources share, so the historical and
daily loaders write to the same row.

### Ingestion

Run the team seed first; everything else foreign-keys to it (the two loaders
do this for you unless you pass `--skip-teams`).

```bash
# Reference data — the 30 clubs
docker compose exec backend python -m app.ingestion.teams

# Historical: the M2 parquet -> games (labels). ~4s for the full 2018-2025 set.
docker compose exec backend python -m app.ingestion.historical
docker compose exec backend python -m app.ingestion.historical --season 2024

# Daily: the M1 schedule -> games (matchup, venue, starters, results)
docker compose exec backend python -m app.ingestion.daily                    # today (US Eastern)
docker compose exec backend python -m app.ingestion.daily --date 2025-07-01
docker compose exec backend python -m app.ingestion.daily --start 2025-07-01 --end 2025-07-07
```

Both loaders are idempotent — a re-run reports `0 inserted, 0 updated` and
changes nothing. They also compose: the historical loader supplies the NRFI
label, the daily loader supplies schedule details, and neither overwrites the
other's columns with nulls. For games that are already final, the daily
loader reads the linescore and writes the first-inning result, so today's
games become labeled training rows the same night.

## Feature engineering (M4)

First, derive per-game first-inning box scores from the cached Statcast
chunks (no network — it re-reads what M2 already downloaded) and load them
into the `pitcher_game_stats` / `team_game_stats` tables:

```bash
docker compose exec backend python -m app.collection.statcast_boxscore   # ~23s for 2018-2025
docker compose exec backend python -m app.ingestion.game_stats           # ~14s
```

Then build the feature matrix:

```bash
docker compose exec backend python -m app.features.pipeline              # -> data/processed/features.parquet
docker compose exec backend python -m app.features.pipeline --date 2026-08-05   # one slate, inference-style
docker compose exec backend python -m app.features.shrinkage             # re-derive the shrinkage constants
```

32 features over ~18k games in about 3 seconds. Two properties matter:

**No leakage.** Every aggregate is a backward `merge_asof` with
`allow_exact_matches=False`, so a game only sees strictly earlier dates.
Deleting years of future data and rebuilding produces byte-identical
features. Same-day games — including both halves of a doubleheader — never
feed each other, because game 1's result isn't available in the morning when
the prediction job actually runs.

**Training and inference are the same call.** `compute_features` runs over
the full history and the caller filters afterwards, so a game's feature row
is identical whether it's computed the morning before or years later. A game
that hasn't been played comes back with full features and a null target.

Rates are shrunk toward the league average so a pitcher's first start doesn't
read as a 100% record. The shrinkage constants are measured, not guessed —
`app.features.shrinkage` decomposes each stat's observed spread into real
talent plus sampling noise. (Sanity check: it returns k=86 batters faced for
first-inning K%, independently reproducing the known ~70 PA stabilization
point.)

## Baseline model (M5)

```bash
docker compose exec backend python -m app.training.baseline
```

Trains a scaled Logistic Regression on `data/processed/features.parquet`
(rebuilding it via M4 if missing), evaluates it on 2024-2026 — seasons the
model never trains on — and checks it against two references fit on the
training set only: always guess the more common label, and always guess the
training NRFI rate. Saves the fitted model and a metrics report to
`data/models/` (gitignored — rerun the command to regenerate).

Full numbers and the reasoning behind the season-based split live in
`docs/milestones.md` under M5.

## Model iteration & selection (M6)

```bash
docker compose exec backend python -m app.training.compare
```

Trains an XGBoost candidate on the same split and features as M5, scores it
against the Logistic Regression baseline on the identical held-out set, and
picks a champion by ROC AUC among whichever candidate(s) clear the M5 gating
bar — with a written, metric-backed reason, not "XGBoost is fancier."
Individual runs are also available:

```bash
docker compose exec backend python -m app.training.xgboost_model   # XGBoost candidate alone
```

Saves the winning model to `data/models/champion.joblib` — the one artifact
M7 will load for daily inference, under a model-agnostic name so the
inference path doesn't need to know which family is in production. Full
numbers, feature importances, and the selection reasoning live in
`docs/milestones.md` under M6.

## Prediction service & daily automation (M7)

```bash
docker compose exec backend python -m app.prediction.job                  # today
docker compose exec backend python -m app.prediction.job --date 2026-08-18
```

Refreshes the date's schedule (M1/M3), narrows to games that are actually
safe to predict — not yet started, both starters announced — computes their
features (M4), scores them with whatever `app.training.compare` most
recently selected as champion (M6), and upserts the results into
`predictions` (M3). Safe to re-run any time; a slate already predicted comes
back `0 inserted, 0 updated, N unchanged`.

A `scheduler` service in `docker-compose.yml` can run this automatically —
it sleeps until 09:00 US/Eastern, runs the job, logs the result, and
repeats. It's opt-in (a Compose *profile*), not part of the default
`docker compose up`, since running it continuously would mean keeping
Docker Desktop — and the machine under it — awake for days just to prove
the loop fires. That's a real cost not worth paying locally; it starts
mattering once M12 puts this somewhere that's actually supposed to stay up.
Start it deliberately when you want to observe it:

```bash
docker compose --profile scheduler up -d scheduler
docker compose logs -f scheduler
```

For now, predictions are kept current with manual runs of the same job the
scheduler would call — no different in what it does, just triggered by a
person instead of a timer.

Full reasoning — why 09:00 ET, the allowlist-of-pre-game-statuses design,
the real bug this surfaced in the M4 feature pipeline (unannounced starters
crashed it), and the decision to defer unattended verification to M12 —
lives in `docs/milestones.md` under M7.

## REST API (M8)

With the backend running (`docker compose up -d`), the full API is live at
`http://localhost:8000` — interactive docs at `/docs`.

```bash
curl "http://localhost:8000/api/games?sort_by=confidence"     # today's slate
curl "http://localhost:8000/api/games/824803"                 # one game, full detail
curl "http://localhost:8000/api/history/accuracy"              # overall/yearly/monthly
curl "http://localhost:8000/api/analytics/pitchers?min_starts=50"
```

Once a game's outcome is known, grade the predictions made for it (nothing
else does this automatically yet — see docs/milestones.md M8):

```bash
docker compose exec backend python -m app.grading.results
```

Traditional pitcher/team stats (ERA, WHIP, FIP, xERA, OPS, OBP, SLG, batting
average) still appear in the response schemas as explicitly nullable fields
returning `null` — no data source for those exists yet (a scope decision,
not an oversight; see `docs/milestones.md` under M8). Everything else —
teams, pitchers, first-inning rate stats, the prediction, its rule-based
explanation, graded history, weather, and odds — is real, live-verified
data.

## Weather & odds collection (M8.5)

Requires `OPENWEATHER_API_KEY` and `ODDS_API_KEY` in `.env` (both free
tier — see `.env.example`). Seed the venue reference table once (coordinates
come straight from the MLB Stats API, not a hand-typed list):

```bash
docker compose exec backend python -m app.ingestion.venues
```

Both sources are then captured automatically as part of the M7 job
(`python -m app.prediction.job`), right after predictions save — one
OpenWeather forecast fetch per unique venue on the slate, one Odds API call
covering the whole day. Both are best-effort: an API failure or an unmatched
game is skipped and logged in the job's output, never fails the run.

```bash
curl "http://localhost:8000/api/games/824803" | python -m json.tool  # weather + odds on a real game
```

### Tests

```bash
docker compose exec backend python -m pytest
```

The suite is fully offline (APIs mocked, in-memory SQLite for the database
tests) — nothing but the container is required.

## Repo structure

```
nrfi-analytics/
├── backend/            FastAPI app
│   ├── alembic/        Migrations (M3)
│   └── app/
│       ├── main.py     Entrypoint, health check
│       ├── config.py   Settings (env-driven)
│       ├── collection/ mlb_stats.py (M1), statcast_backfill.py (M2), statcast_boxscore.py (M4), weather.py + odds.py (M8.5)
│       ├── db/         Engine, session, declarative base (M3)
│       ├── models/     ORM tables (M3), venue.py (M8.5)
│       ├── ingestion/  Loaders: teams, historical, daily (M3), game_stats (M4), venues (M8.5)
│       ├── features/   As-of feature pipeline + shrinkage estimator (M4)
│       ├── training/   Split, baseline (M5), XGBoost + comparison/selection (M6)
│       ├── prediction/ Inference, storage, daily job + scheduler (M7), weather/odds enrichment (M8.5)
│       ├── grading/    Prediction vs. actual-outcome grading (M8)
│       ├── schemas/    Pydantic response models (M8)
│       ├── queries/    Read-only DB queries + explanation generator (M8)
│       └── routers/    games, history, analytics endpoints (M8)
├── frontend/           React + TypeScript + Tailwind (Vite)
│   └── src/
│       ├── App.tsx     Placeholder page — becomes M9 dashboard
│       └── main.tsx    Entrypoint
├── docs/               Planning documents (this is the source of truth)
├── docker-compose.yml  Postgres + backend + frontend, one command (+ opt-in scheduler)
├── .env.example        Required env vars, no real secrets
└── README.md           This file
```

## Running without Docker (optional)

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

You'll need a local Postgres instance and a `.env` pointing
`DATABASE_URL` at it if you're not using the Docker Compose Postgres
container.
