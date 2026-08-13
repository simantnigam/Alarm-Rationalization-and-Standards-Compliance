"""Shared test infrastructure: a single session-scoped Postgres testcontainer, reused
by every phase that needs a real database (D-05 rejects SQLite -- Postgres is the only
engine, so tests run against the real thing via testcontainers).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from testcontainers.community.postgres import PostgresContainer


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
