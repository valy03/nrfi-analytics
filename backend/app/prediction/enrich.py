"""M8.5 — weather + odds enrichment, run alongside the M7 job.

Both are display-only (research.md) and deliberately best-effort: a failure
here must never block predictions, which are the actual product. Each game
is resolved and written independently, so one game's failure — an unknown
venue, no odds posted yet, a transient API error — never affects any other
game's weather/odds, or predictions at all.

Scoped to the same game_pks app.prediction.job already decided are eligible
to predict — weather/odds are captured on the same cadence as predictions,
not for games already underway or decided.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collection import odds as odds_collection
from app.collection import weather as weather_collection
from app.ingestion.upsert import UpsertCounts, upsert_rows
from app.models import Game, Team, Venue


def enrich_weather(session: Session, game_pks: list[int]) -> UpsertCounts:
    """One OpenWeather forecast fetch per unique venue among ``game_pks`` —
    a doubleheader shares a venue and only costs one call, not two.
    """
    if not game_pks:
        return UpsertCounts()

    games = session.scalars(select(Game).where(Game.game_pk.in_(game_pks))).all()
    games_with_venue = [g for g in games if g.venue_id and g.start_time_utc]
    if not games_with_venue:
        return UpsertCounts()

    venue_ids = {g.venue_id for g in games_with_venue}
    venues = {
        v.id: v for v in session.scalars(select(Venue).where(Venue.id.in_(venue_ids)))
    }

    forecast_cache: dict[int, list[dict]] = {}
    rows = []
    for game in games_with_venue:
        venue = venues.get(game.venue_id)
        if venue is None:
            continue  # not one of the parks app.ingestion.venues knows about

        if venue.id not in forecast_cache:
            try:
                forecast_cache[venue.id] = weather_collection.fetch_forecast(
                    venue.latitude, venue.longitude
                )
            except weather_collection.WeatherAPIError:
                forecast_cache[venue.id] = []

        reading = weather_collection.reading_from_entries(
            forecast_cache[venue.id], game.start_time_utc
        )
        if reading is None:
            continue
        rows.append(
            {
                "game_pk": game.game_pk,
                "weather_temp_f": reading.temp_f,
                "weather_conditions": reading.conditions,
                "weather_wind_mph": reading.wind_mph,
                "weather_wind_direction_deg": reading.wind_direction_deg,
                "weather_captured_at": reading.captured_at,
            }
        )

    if not rows:
        return UpsertCounts()
    return upsert_rows(session, Game, rows, key_cols=["game_pk"])


def enrich_odds(session: Session, game_pks: list[int]) -> UpsertCounts:
    """One Odds API call total, covering the whole slate."""
    if not game_pks:
        return UpsertCounts()

    games = session.scalars(select(Game).where(Game.game_pk.in_(game_pks))).all()
    if not games:
        return UpsertCounts()

    team_ids = {g.home_team_id for g in games} | {g.away_team_id for g in games}
    teams = {t.id: t for t in session.scalars(select(Team).where(Team.id.in_(team_ids)))}

    try:
        moneylines = odds_collection.todays_moneylines()
    except odds_collection.OddsAPIError:
        return UpsertCounts()

    rows = []
    for game in games:
        home_team = teams.get(game.home_team_id)
        away_team = teams.get(game.away_team_id)
        if home_team is None or away_team is None:
            continue
        line = moneylines.get((home_team.name, away_team.name))
        if line is None:
            continue
        rows.append(
            {
                "game_pk": game.game_pk,
                "home_moneyline": line.home_moneyline,
                "away_moneyline": line.away_moneyline,
                "odds_bookmaker": line.bookmaker,
                "odds_captured_at": line.captured_at,
            }
        )

    if not rows:
        return UpsertCounts()
    return upsert_rows(session, Game, rows, key_cols=["game_pk"])
