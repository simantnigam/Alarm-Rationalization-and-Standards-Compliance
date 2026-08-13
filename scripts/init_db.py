"""Provisions the two roles and two databases D-05 requires: `alarmapi_rw` owns
`alarmdb`; `copilot_rw` owns `copilot`. Neither role may connect to the other's
database -- Postgres grants CONNECT to PUBLIC by default, so this explicitly revokes
it rather than merely not granting it.

Runnable standalone (mirrors what a docker-entrypoint-initdb.d hook or a compose init
step would call) and imported directly by tests against a real Postgres testcontainer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from psycopg import sql


@dataclass(frozen=True)
class ProvisionSpec:
    copilot_db: str
    copilot_user: str
    copilot_password: str
    alarmdb: str
    alarmapi_user: str
    alarmapi_password: str


def _role_exists(cur: psycopg.Cursor[tuple[int]], role: str) -> bool:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    return cur.fetchone() is not None


def _database_exists(cur: psycopg.Cursor[tuple[int]], name: str) -> bool:
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    return cur.fetchone() is not None


def _create_role_if_missing(cur: psycopg.Cursor[tuple[int]], role: str, password: str) -> None:
    if _role_exists(cur, role):
        return
    cur.execute(
        sql.SQL("CREATE ROLE {role} WITH LOGIN PASSWORD {password}").format(
            role=sql.Identifier(role), password=sql.Literal(password)
        )
    )


def _create_database_if_missing(cur: psycopg.Cursor[tuple[int]], name: str, owner: str) -> None:
    if _database_exists(cur, name):
        return
    cur.execute(
        sql.SQL("CREATE DATABASE {name} OWNER {owner}").format(
            name=sql.Identifier(name), owner=sql.Identifier(owner)
        )
    )


def _lock_database_to_owner(cur: psycopg.Cursor[tuple[int]], database: str, owner: str) -> None:
    """No role but `owner` (and superusers) may connect to `database`."""
    cur.execute(
        sql.SQL("REVOKE ALL ON DATABASE {db} FROM PUBLIC").format(db=sql.Identifier(database))
    )
    cur.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {db} TO {owner}").format(
            db=sql.Identifier(database), owner=sql.Identifier(owner)
        )
    )


def provision_roles_and_databases(superuser_dsn: str, spec: ProvisionSpec) -> None:
    """Idempotent: safe to call on every container start, not just the first."""
    with psycopg.connect(superuser_dsn, autocommit=True) as conn, conn.cursor() as cur:
        _create_role_if_missing(cur, spec.alarmapi_user, spec.alarmapi_password)
        _create_role_if_missing(cur, spec.copilot_user, spec.copilot_password)
        _create_database_if_missing(cur, spec.alarmdb, spec.alarmapi_user)
        _create_database_if_missing(cur, spec.copilot_db, spec.copilot_user)

        # Explicit revoke-then-grant, not "skip granting" -- PUBLIC has CONNECT on every
        # database by default, so the boundary does not exist until this runs.
        _lock_database_to_owner(cur, spec.alarmdb, spec.alarmapi_user)
        _lock_database_to_owner(cur, spec.copilot_db, spec.copilot_user)


def _spec_from_env() -> ProvisionSpec:
    return ProvisionSpec(
        copilot_db=os.environ.get("COPILOT_DB_NAME", "copilot"),
        copilot_user=os.environ.get("COPILOT_DB_USER", "copilot_rw"),
        copilot_password=os.environ["COPILOT_DB_PASSWORD"],
        alarmdb=os.environ.get("ALARMDB_NAME", "alarmdb"),
        alarmapi_user=os.environ.get("ALARMDB_USER", "alarmapi_rw"),
        alarmapi_password=os.environ["ALARMDB_PASSWORD"],
    )


def main() -> None:
    superuser_dsn = os.environ["POSTGRES_SUPERUSER_DSN"]
    provision_roles_and_databases(superuser_dsn, _spec_from_env())


if __name__ == "__main__":
    main()
