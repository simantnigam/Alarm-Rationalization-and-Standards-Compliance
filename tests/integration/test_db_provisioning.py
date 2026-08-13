"""Runtime enforcement of the MCP boundary (D-05): copilot_rw must have no grant on
alarmdb, and -- symmetrically, for defense in depth -- alarmapi_rw must have no grant
on the copilot database. Postgres grants CONNECT to PUBLIC by default, so this is only
real if provisioning explicitly revokes it, not merely skips granting it.
"""

from __future__ import annotations

import psycopg
import pytest
from scripts.init_db import ProvisionSpec, provision_roles_and_databases

SPEC = ProvisionSpec(
    copilot_db="copilot_test",
    copilot_user="copilot_rw_test",
    copilot_password="copilot-test-pw",
    alarmdb="alarmdb_test",
    alarmapi_user="alarmapi_rw_test",
    alarmapi_password="alarmapi-test-pw",
)


@pytest.fixture(scope="module")
def provisioned(postgres_superuser_dsn: str) -> ProvisionSpec:
    provision_roles_and_databases(postgres_superuser_dsn, SPEC)
    # Re-running must be safe -- this is what a restarted container's initdb hook does.
    provision_roles_and_databases(postgres_superuser_dsn, SPEC)
    return SPEC


def _dsn(host_port: tuple[str, int], user: str, password: str, dbname: str) -> str:
    host, port = host_port
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def test_alarmapi_rw_can_connect_to_alarmdb(
    provisioned: ProvisionSpec, postgres_host_port: tuple[str, int]
) -> None:
    conn = psycopg.connect(
        _dsn(
            postgres_host_port,
            provisioned.alarmapi_user,
            provisioned.alarmapi_password,
            provisioned.alarmdb,
        )
    )
    conn.close()


def test_copilot_rw_can_connect_to_copilot_db(
    provisioned: ProvisionSpec, postgres_host_port: tuple[str, int]
) -> None:
    conn = psycopg.connect(
        _dsn(
            postgres_host_port,
            provisioned.copilot_user,
            provisioned.copilot_password,
            provisioned.copilot_db,
        )
    )
    conn.close()


def test_copilot_rw_cannot_connect_to_alarmdb(
    provisioned: ProvisionSpec, postgres_host_port: tuple[str, int]
) -> None:
    """The assignment's central rule, enforced at the database, not just by import-linter."""
    with pytest.raises(psycopg.OperationalError, match=r"permission denied|denied to connect"):
        psycopg.connect(
            _dsn(
                postgres_host_port,
                provisioned.copilot_user,
                provisioned.copilot_password,
                provisioned.alarmdb,
            )
        )


def test_alarmapi_rw_cannot_connect_to_copilot_db(
    provisioned: ProvisionSpec, postgres_host_port: tuple[str, int]
) -> None:
    with pytest.raises(psycopg.OperationalError, match=r"permission denied|denied to connect"):
        psycopg.connect(
            _dsn(
                postgres_host_port,
                provisioned.alarmapi_user,
                provisioned.alarmapi_password,
                provisioned.copilot_db,
            )
        )
