"""Shared, session-scoped seeded alarmdb + FastAPI app for every simulator route test.
Seeding the compact profile is not free (~46k rows) so it happens exactly once per
test session, not once per test module.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from scripts.init_db import ProvisionSpec, provision_roles_and_databases
from sqlalchemy import Engine, create_engine

from alarm_api_simulator.config import SimulatorSettings
from alarm_api_simulator.db.schema import metadata
from alarm_api_simulator.main import create_app
from alarm_api_simulator.seed.generator import generate_dataset
from alarm_api_simulator.seed.loader import load_dataset

SIM_SEED = 20260812
SIM_NOW = datetime(2026, 8, 13, tzinfo=UTC)
TEST_TOKEN = "test-alarm-api-token"

_SPEC = ProvisionSpec(
    copilot_db="copilot_sim_api_test",
    copilot_user="copilot_rw_sim_api_test",
    copilot_password="copilot-test-pw",
    alarmdb="alarmdb_sim_api_test",
    alarmapi_user="alarmapi_rw_sim_api_test",
    alarmapi_password="alarmapi-test-pw",
)


@pytest.fixture(scope="session")
def seeded_alarmdb_engine(
    postgres_superuser_dsn: str, postgres_host_port: tuple[str, int]
) -> Engine:
    provision_roles_and_databases(postgres_superuser_dsn, _SPEC)
    host, port = postgres_host_port
    dsn = (
        f"postgresql+psycopg://{_SPEC.alarmapi_user}:{_SPEC.alarmapi_password}"
        f"@{host}:{port}/{_SPEC.alarmdb}"
    )
    engine = create_engine(dsn)
    metadata.drop_all(engine)
    metadata.create_all(engine)
    dataset = generate_dataset(profile="compact", seed=SIM_SEED, now=SIM_NOW)
    load_dataset(engine, dataset)
    return engine


@pytest.fixture(scope="session")
def simulator_settings() -> SimulatorSettings:
    return SimulatorSettings(
        alarm_api_token=TEST_TOKEN,
        alarmdb_password="unused-dsn-built-directly",
        sim_profile="compact",
        sim_seed=SIM_SEED,
        sim_now=SIM_NOW.isoformat(),
    )


@pytest.fixture(scope="session")
def api_client(seeded_alarmdb_engine: Engine, simulator_settings: SimulatorSettings) -> TestClient:
    app = create_app(engine=seeded_alarmdb_engine, settings=simulator_settings)
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}
