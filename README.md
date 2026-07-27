# NRFI Analytics

Transparent, data-driven No Run First Inning (NRFI) predictions for every
MLB game — explaining *why* a prediction was made, not just displaying a
confidence score.

See `docs/` for the full planning trail: `planning.md`, `requirements.md`,
`research.md`, `milestones.md`, `wireframes.md`. This README only covers
running what exists right now (M0).

---

## Status

**M0 — Project Scaffolding.** See `docs/milestones.md` for the full
roadmap. Nothing real happens yet — this milestone just proves the stack
boots end to end: Postgres up, backend health check responding, frontend
loading and successfully calling the backend.

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

## Repo structure

```
nrfi-analytics/
├── backend/            FastAPI app
│   └── app/
│       ├── main.py     Entrypoint, health check
│       ├── config.py   Settings (env-driven)
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
