"""Team seeding (M3).

The 30 clubs are a fixed reference table that everything else foreign-keys
to, so this runs before either data loader. Source is the MLB Stats API,
which gives the canonical id/name/abbreviation triple.

Run it:
    python -m app.ingestion.teams
"""

from __future__ import annotations

import statsapi
from sqlalchemy.orm import Session

from app.db.session import session_scope
from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Team

# Statcast identifies teams by abbreviation only, and its codes matched the
# MLB Stats API's exactly across the whole 2018-2025 backfill (Savant
# retroactively applies current codes, so 2018 Oakland games already read
# "ATH"). These aliases are belt-and-braces for other pybaseball endpoints
# and older exports, which still use the legacy forms.
ABBREVIATION_ALIASES = {
    "ARI": "AZ",
    "CHW": "CWS",
    "FLA": "MIA",
    "KCR": "KC",
    "LA": "LAD",
    "NYA": "NYY",
    "NYN": "NYM",
    "OAK": "ATH",
    "SDP": "SD",
    "SFG": "SF",
    "TBR": "TB",
    "WSN": "WSH",
}


class TeamIngestionError(RuntimeError):
    """Raised when the team reference table can't be built."""


def fetch_teams() -> list[dict]:
    """Return the 30 active MLB clubs as ``teams`` row dicts."""
    try:
        payload = statsapi.get("teams", {"sportId": 1})
    except Exception as exc:
        raise TeamIngestionError(f"Failed to fetch MLB teams: {exc}") from exc

    rows = []
    for team in payload.get("teams", []):
        rows.append(
            {
                "id": team["id"],
                "name": team["name"],
                "abbreviation": team["abbreviation"],
                "team_code": team.get("teamCode"),
                "league": (team.get("league") or {}).get("name"),
                "division": (team.get("division") or {}).get("name"),
            }
        )
    if not rows:
        raise TeamIngestionError("MLB teams endpoint returned no teams")
    return rows


def seed_teams(session: Session) -> UpsertCounts:
    """Insert/update the team reference table."""
    return upsert_rows(session, Team, fetch_teams(), key_cols=["id"])


def team_id_by_abbreviation(session: Session) -> dict[str, int]:
    """Lookup used by the Statcast loader, which only has team codes.

    Includes the legacy aliases so an older abbreviation still resolves.
    """
    lookup = {t.abbreviation: t.id for t in session.query(Team).all()}
    for alias, current in ABBREVIATION_ALIASES.items():
        if current in lookup:
            lookup.setdefault(alias, lookup[current])
    return lookup


def main(argv: list[str] | None = None) -> int:
    try:
        with session_scope() as session:
            counts = seed_teams(session)
    except TeamIngestionError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Teams: {counts} ({counts.total} total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
