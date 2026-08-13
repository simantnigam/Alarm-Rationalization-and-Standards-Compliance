"""Bulk-loads a generated SeedDataset into alarmdb. Parent tables before children
(sites/units/assets/alarm_definitions before alarms) so foreign keys are always valid.
"""

from __future__ import annotations

from sqlalchemy import Engine, delete, insert

from alarm_api_simulator.db.schema import (
    alarm_definitions,
    alarms,
    assets,
    kpi_definitions,
    sites,
    units,
)
from alarm_api_simulator.seed.generator import SeedDataset

_BATCH_SIZE = 5000


def _bulk_insert(conn, table, rows: list[dict]) -> None:  # type: ignore[no-untyped-def]
    if not rows:
        return
    for start in range(0, len(rows), _BATCH_SIZE):
        conn.execute(insert(table), rows[start : start + _BATCH_SIZE])


def load_dataset(engine: Engine, dataset: SeedDataset, *, truncate_first: bool = False) -> None:
    with engine.begin() as conn:
        if truncate_first:
            # Children before parents, respecting foreign keys.
            conn.execute(delete(alarms))
            conn.execute(delete(alarm_definitions))
            conn.execute(delete(assets))
            conn.execute(delete(units))
            conn.execute(delete(sites))
            conn.execute(delete(kpi_definitions))

        _bulk_insert(conn, sites, dataset.sites)
        _bulk_insert(conn, units, dataset.units)
        _bulk_insert(conn, assets, dataset.assets)
        _bulk_insert(conn, alarm_definitions, dataset.alarm_definitions)
        _bulk_insert(conn, alarms, dataset.alarms)
        _bulk_insert(conn, kpi_definitions, dataset.kpi_definitions)
