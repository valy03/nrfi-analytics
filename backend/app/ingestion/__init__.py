"""Ingestion (M3): move collected data into Postgres.

Three loaders, all idempotent:

- ``teams``      — seeds the 30 clubs from the MLB Stats API (run first;
                   everything else foreign-keys to it)
- ``historical`` — the M2 Statcast parquet -> ``games`` (labels)
- ``daily``      — the M1 schedule -> ``games`` (matchups, pitchers, results)
"""

from app.ingestion.upsert import upsert_rows

__all__ = ["upsert_rows"]
