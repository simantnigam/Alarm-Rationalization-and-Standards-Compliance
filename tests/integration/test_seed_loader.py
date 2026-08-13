"""The loader must move a generated SeedDataset into alarmdb intact -- same row counts,
same referential order (sites/units/assets/alarm_definitions before alarms).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.init_db import ProvisionSpec, provision_roles_and_databases
from sqlalchemy import Engine, create_engine, func, select

from alarm_api_simulator.db.schema import alarm_definitions, alarms, assets, metadata, sites, units
from alarm_api_simulator.seed.generator import generate_dataset
from alarm_api_simulator.seed.loader import load_dataset

SPEC = ProvisionSpec(
    copilot_db="copilot_loader_test",
    copilot_user="copilot_rw_loader_test",
    copilot_password="copilot-test-pw",
    alarmdb="alarmdb_loader_test",
    alarmapi_user="alarmapi_rw_loader_test",
    alarmapi_password="alarmapi-test-pw",
)


@pytest.fixture(scope="module")
def alarmdb_engine(postgres_superuser_dsn: str, postgres_host_port: tuple[str, int]) -> Engine:
    provision_roles_and_databases(postgres_superuser_dsn, SPEC)
    host, port = postgres_host_port
    dsn = (
        f"postgresql+psycopg://{SPEC.alarmapi_user}:{SPEC.alarmapi_password}"
        f"@{host}:{port}/{SPEC.alarmdb}"
    )
    engine = create_engine(dsn)
    metadata.drop_all(engine)
    metadata.create_all(engine)
    return engine


def test_load_dataset_inserts_every_row(alarmdb_engine: Engine) -> None:
    dataset = generate_dataset(
        profile="compact", seed=20260812, now=datetime(2026, 8, 13, tzinfo=UTC)
    )
    load_dataset(alarmdb_engine, dataset)

    with alarmdb_engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(sites)).scalar_one() == len(
            dataset.sites
        )
        assert conn.execute(select(func.count()).select_from(units)).scalar_one() == len(
            dataset.units
        )
        assert conn.execute(select(func.count()).select_from(assets)).scalar_one() == len(
            dataset.assets
        )
        assert conn.execute(
            select(func.count()).select_from(alarm_definitions)
        ).scalar_one() == len(dataset.alarm_definitions)
        assert conn.execute(select(func.count()).select_from(alarms)).scalar_one() == len(
            dataset.alarms
        )


def test_load_dataset_is_idempotent_on_a_clean_reseed(alarmdb_engine: Engine) -> None:
    """Reseeding (e.g. container restart in the demo profile) must not duplicate rows."""
    dataset = generate_dataset(
        profile="compact", seed=20260812, now=datetime(2026, 8, 13, tzinfo=UTC)
    )
    load_dataset(alarmdb_engine, dataset, truncate_first=True)
    load_dataset(alarmdb_engine, dataset, truncate_first=True)

    with alarmdb_engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(alarms)).scalar_one() == len(
            dataset.alarms
        )
