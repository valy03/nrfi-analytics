"""NRFI Analytics API entrypoint.

M0 scope: just enough to prove the backend boots, talks to config,
and responds to a health check. Real routers (games, predictions,
history, analytics) get added starting at M8 per milestones.md.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="NRFI Analytics API",
    description="Transparent, data-driven NRFI predictions for MLB games.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic liveness check. M0 exit criteria: this returns 200."""
    return {"status": "ok", "service": "nrfi-analytics-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NRFI Analytics API — see /docs for endpoints"}
