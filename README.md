# NRFI Analytics

Transparent, data-driven No Run First Inning (NRFI) predictions for every
MLB game — explaining *why* a prediction was made, not just displaying a
confidence score.

See `docs/` for the full planning trail: `planning.md`, `requirements.md`,
`research.md`, `milestones.md`, `wireframes.md`. This README only covers
running what exists right now (M0).

---

## Status

**M3 — Database Schema & Ingestion (done).** On top of the M0 scaffolding,
the backend can pull the daily MLB schedule and probable starting pitchers
(M1), backfill historical Statcast pitch data into a per-game NRFI-labeled
dataset (M2), and load both into PostgreSQL behind Alembic migrations (M3).
Next up is M4, the feature engineering pipeline. See `docs/milestones.md` for
the full roadmap.

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
│       ├── collection/ Data collection — mlb_stats.py (M1), statcast_backfill.py (M2)
│       ├── db/         Engine, session, declarative base (M3)
│       ├── models/     ORM tables (M3)
│       ├── ingestion/  Loaders: teams, historical (M2 -> DB), daily (M1 -> DB)
│       └── routers/    Empty for now — populated starting M8
├── frontend/           React + TypeScript + Tailwind (Vite)
│   └── src/
│       ├── App.tsx     Placeholder page — becomes M9 dashboard
│       └── main.tsx    Entrypoint
├── docs/               Planning documents (this is the source of truth)
├── docker-compose.yml  Postgres + backend + frontend, one command
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
