"""Shared test infrastructure: one session-scoped Postgres testcontainer (D-05 rejects
SQLite -- Postgres is the only engine), one seeded simulator, one MCP server, and one
FastEmbed embedder, reused across tests/unit, tests/integration, and tests/e2e. This is
what the walking-skeleton E2E test (Phase 2.5) and every phase after it build on.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import uvicorn
from fastapi.testclient import TestClient
from scripts.init_db import ProvisionSpec, provision_roles_and_databases
from sqlalchemy import Engine, create_engine
from testcontainers.community.postgres import PostgresContainer

from alarm_api_simulator.config import SimulatorSettings
from alarm_api_simulator.db.schema import metadata
from alarm_api_simulator.main import create_app
from alarm_api_simulator.seed.generator import generate_dataset
from alarm_api_simulator.seed.loader import load_dataset
from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.server import build_server
from rag.ingestion.embedder import Embedder

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


def _as_psycopg_dsn(sqlalchemy_url: str) -> str:
    """testcontainers returns a SQLAlchemy-style URL (postgresql+psycopg2://...);
    psycopg3 wants a bare postgresql:// DSN.
    """
    return sqlalchemy_url.replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def postgres_superuser_dsn(postgres_container: PostgresContainer) -> str:
    return _as_psycopg_dsn(postgres_container.get_connection_url())


@pytest.fixture(scope="session")
def postgres_host_port(postgres_container: PostgresContainer) -> tuple[str, int]:
    host = postgres_container.get_container_host_ip()
    port = int(postgres_container.get_exposed_port(postgres_container.port))
    return host, port


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


@pytest.fixture(scope="session")
def alarm_api_test_token() -> str:
    return TEST_TOKEN


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="session")
def live_simulator_url(
    seeded_alarmdb_engine: Engine, simulator_settings: SimulatorSettings
) -> Iterator[str]:
    """The simulator over a real socket -- what the connector and the MCP server
    actually talk to. Session-scoped: one process serves every test that needs a real
    (not in-process TestClient) Alarm API.
    """
    app = create_app(engine=seeded_alarmdb_engine, settings=simulator_settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def mcp_alarm_server_url(live_simulator_url: str, alarm_api_test_token: str) -> Iterator[str]:
    """The alarm-management MCP server over real streamable-HTTP, backed by the real
    (seeded) simulator -- what the copilot's MCP client actually talks to.
    """
    settings = AlarmMcpSettings(
        alarm_api_base_url=live_simulator_url, alarm_api_token=alarm_api_test_token
    )
    mcp = build_server(settings)
    app = mcp.streamable_http_app()

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
