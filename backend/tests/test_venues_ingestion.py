"""Tests for M8.5 venue seeding (app.ingestion.venues).

The MLB Stats API is stubbed at the two endpoints venues.py actually calls
— "teams" (to discover each club's home venue id) and "venue" (to hydrate
coordinates) — same pattern test_ingestion.py uses for team seeding.
"""

import pytest

from app.ingestion import venues as venues_ingest
from app.models import Venue

TEAMS_PAYLOAD = {
    "teams": [
        {"id": 111, "name": "Boston Red Sox", "venue": {"id": 3, "name": "Fenway Park"}},
        {"id": 147, "name": "New York Yankees", "venue": {"id": 3313, "name": "Yankee Stadium"}},
    ]
}

VENUES_PAYLOAD = {
    "venues": [
        {
            "id": 3,
            "name": "Fenway Park",
            "location": {
                "city": "Boston",
                "defaultCoordinates": {"latitude": 42.346456, "longitude": -71.097441},
            },
        },
        {
            "id": 3313,
            "name": "Yankee Stadium",
            "location": {
                "city": "Bronx",
                "defaultCoordinates": {"latitude": 40.82919482, "longitude": -73.9264977},
            },
        },
    ]
}


def _stub_statsapi(monkeypatch, teams_payload=TEAMS_PAYLOAD, venues_payload=VENUES_PAYLOAD):
    def fake_get(endpoint, params=None, **kwargs):
        if endpoint == "teams":
            return teams_payload
        if endpoint == "venue":
            return venues_payload
        raise AssertionError(f"unexpected endpoint {endpoint}")

    monkeypatch.setattr(venues_ingest.statsapi, "get", fake_get)


def test_seed_venues_inserts_coordinates(session, monkeypatch):
    _stub_statsapi(monkeypatch)

    counts = venues_ingest.seed_venues(session)

    assert counts.inserted == 2
    fenway = session.get(Venue, 3)
    assert fenway.name == "Fenway Park"
    assert fenway.city == "Boston"
    assert float(fenway.latitude) == pytest.approx(42.346456)
    assert float(fenway.longitude) == pytest.approx(-71.097441)


def test_seed_venues_is_idempotent(session, monkeypatch):
    _stub_statsapi(monkeypatch)

    venues_ingest.seed_venues(session)
    counts = venues_ingest.seed_venues(session)

    assert counts.inserted == 0 and counts.updated == 0
    assert session.query(Venue).count() == 2


def test_seed_venues_updates_a_renamed_park(session, monkeypatch):
    _stub_statsapi(monkeypatch)
    venues_ingest.seed_venues(session)

    renamed = {
        "venues": [
            dict(VENUES_PAYLOAD["venues"][0], name="New Sponsor Field at Fenway"),
            VENUES_PAYLOAD["venues"][1],
        ]
    }
    _stub_statsapi(monkeypatch, venues_payload=renamed)

    counts = venues_ingest.seed_venues(session)

    assert counts.updated == 1
    assert session.get(Venue, 3).name == "New Sponsor Field at Fenway"


def test_seed_venues_skips_a_venue_with_no_coordinates(session, monkeypatch):
    missing_coords = {
        "venues": [
            {"id": 3, "name": "Fenway Park", "location": {"city": "Boston"}},
            VENUES_PAYLOAD["venues"][1],
        ]
    }
    _stub_statsapi(monkeypatch, venues_payload=missing_coords)

    counts = venues_ingest.seed_venues(session)

    assert counts.inserted == 1
    assert session.get(Venue, 3) is None
    assert session.get(Venue, 3313) is not None


def test_fetch_venues_raises_when_teams_endpoint_returns_nothing(monkeypatch):
    _stub_statsapi(monkeypatch, teams_payload={"teams": []})

    with pytest.raises(venues_ingest.VenueIngestionError):
        venues_ingest.fetch_venues()


def test_fetch_venues_raises_when_no_venue_has_coordinates(monkeypatch):
    _stub_statsapi(
        monkeypatch,
        venues_payload={"venues": [{"id": 3, "name": "Fenway Park", "location": {}}]},
    )

    with pytest.raises(venues_ingest.VenueIngestionError):
        venues_ingest.fetch_venues()
