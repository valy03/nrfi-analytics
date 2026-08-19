"""Venue seeding (M8.5): the ~30 active parks' coordinates, for weather.

Same shape as app.ingestion.teams — a small, mostly-static reference table,
refreshed on demand rather than tied to any other loader. Source is the MLB
Stats API's venue endpoint with location hydration, which returns real
lat/lon (``defaultCoordinates``) directly, so there's no hand-typed
coordinate table to keep in sync when a park is renamed or a team relocates.

Run it:
    python -m app.ingestion.venues
"""

from __future__ import annotations

import statsapi
from sqlalchemy.orm import Session

from app.db.session import session_scope
from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Venue


class VenueIngestionError(RuntimeError):
    """Raised when the venue reference table can't be built."""


def _active_venue_ids() -> list[int]:
    """Each active club's home ballpark id, from the teams endpoint."""
    try:
        payload = statsapi.get("teams", {"sportId": 1})
    except Exception as exc:
        raise VenueIngestionError(f"Failed to fetch MLB teams: {exc}") from exc

    ids = {t["venue"]["id"] for t in payload.get("teams", []) if t.get("venue")}
    if not ids:
        raise VenueIngestionError("MLB teams endpoint returned no venues")
    return sorted(ids)


def fetch_venues() -> list[dict]:
    """Active parks as ``venues`` row dicts, coordinates included."""
    venue_ids = _active_venue_ids()
    try:
        payload = statsapi.get(
            "venue",
            {"venueIds": ",".join(map(str, venue_ids)), "hydrate": "location"},
        )
    except Exception as exc:
        raise VenueIngestionError(f"Failed to fetch venue details: {exc}") from exc

    rows = []
    for venue in payload.get("venues", []):
        location = venue.get("location") or {}
        coords = location.get("defaultCoordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if lat is None or lon is None:
            continue  # no usable coordinates on this venue — skip, don't guess
        rows.append(
            {
                "id": venue["id"],
                "name": venue["name"],
                "city": location.get("city"),
                "latitude": lat,
                "longitude": lon,
            }
        )
    if not rows:
        raise VenueIngestionError("No venues had usable coordinates")
    return rows


def seed_venues(session: Session) -> UpsertCounts:
    return upsert_rows(session, Venue, fetch_venues(), key_cols=["id"])


def main(argv: list[str] | None = None) -> int:
    try:
        with session_scope() as session:
            counts = seed_venues(session)
    except VenueIngestionError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Venues: {counts} ({counts.total} total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
