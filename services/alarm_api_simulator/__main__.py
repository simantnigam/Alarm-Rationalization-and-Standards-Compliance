"""Standalone entrypoint: `python -m alarm_api_simulator`. Also the `alarm-api`
container command in docker-compose (D-10).
"""

from __future__ import annotations

from datetime import UTC, datetime

import uvicorn
from sqlalchemy import func, select

from alarm_api_simulator.config import SimulatorSettings
from alarm_api_simulator.db.engine import build_dsn, create_alarmdb_engine
from alarm_api_simulator.db.schema import alarms, metadata
from alarm_api_simulator.main import create_app
from alarm_api_simulator.seed.generator import generate_dataset
from alarm_api_simulator.seed.loader import load_dataset


def resolve_sim_now(settings: SimulatorSettings) -> datetime:
    if settings.sim_now:
        return datetime.fromisoformat(settings.sim_now)
    return datetime.now(UTC)


def main() -> None:  # pragma: no cover -- process entrypoint, exercised via docker-compose
    settings = SimulatorSettings()  # type: ignore[call-arg]
    dsn = build_dsn(
        host=settings.alarmdb_host,
        port=settings.alarmdb_port,
        user=settings.alarmdb_user,
        password=settings.alarmdb_password,
        database=settings.alarmdb_name,
    )
    engine = create_alarmdb_engine(dsn)
    metadata.create_all(engine)

    with engine.connect() as conn:
        is_empty = conn.execute(select(func.count()).select_from(alarms)).scalar_one() == 0

    if settings.reseed_on_start or is_empty:
        dataset = generate_dataset(
            profile=settings.sim_profile, seed=settings.sim_seed, now=resolve_sim_now(settings)
        )
        load_dataset(engine, dataset, truncate_first=True)

    app = create_app(engine=engine, settings=settings)
    uvicorn.run(app, host=settings.alarm_api_host, port=settings.alarm_api_port)


if __name__ == "__main__":  # pragma: no cover
    main()
