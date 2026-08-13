"""Filtered row fetch shared by every analytics endpoint. Bound parameters only --
filters build a SQLAlchemy Core WHERE clause, never a string-interpolated query.
Aggregation happens in Python (analytics/aggregation.py); the simulator's data volume
does not warrant push-down aggregate SQL, and pure-Python aggregation is far easier to
unit test and reason about.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, select

from alarm_api_simulator.db.schema import alarms


def fetch_filtered_alarms(
    engine: Engine,
    *,
    asset_ids: Sequence[str] | None = None,
    unit: str | None = None,
    site: str | None = None,
    severity: Sequence[str] | None = None,
    alarm_types: Sequence[str] | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict[str, Any]]:
    stmt = select(alarms)
    if asset_ids:
        stmt = stmt.where(alarms.c.asset_id.in_(asset_ids))
    if unit:
        stmt = stmt.where(alarms.c.unit == unit)
    if site:
        stmt = stmt.where(alarms.c.site == site)
    if severity:
        stmt = stmt.where(alarms.c.severity.in_(severity))
    if alarm_types:
        stmt = stmt.where(alarms.c.alarm_type.in_(alarm_types))
    if start_time:
        stmt = stmt.where(alarms.c.start_time >= start_time)
    if end_time:
        stmt = stmt.where(alarms.c.start_time <= end_time)

    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(stmt).mappings().all()]
