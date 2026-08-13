"""alarmdb schema: structural soundness (tables, foreign keys, check constraints) proven
against a real Postgres, not just declared in Python.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from scripts.init_db import ProvisionSpec, provision_roles_and_databases
from sqlalchemy import Engine, create_engine, insert, inspect, select
from sqlalchemy.exc import DataError, IntegrityError

from alarm_api_simulator.db.schema import (
    alarm_definitions,
    alarms,
    assets,
    calculation_runs,
    kpi_definitions,
    metadata,
    sites,
    units,
)

SPEC = ProvisionSpec(
    copilot_db="copilot_schema_test",
    copilot_user="copilot_rw_schema_test",
    copilot_password="copilot-test-pw",
    alarmdb="alarmdb_schema_test",
    alarmapi_user="alarmapi_rw_schema_test",
    alarmapi_password="alarmapi-test-pw",
)


@pytest.fixture(scope="module")
def alarmdb_engine(postgres_superuser_dsn: str, postgres_host_port: tuple[str, int]) -> Engine:
    provision_roles_and_databases(postgres_superuser_dsn, SPEC)
    host, port = postgres_host_port
    dsn = f"postgresql+psycopg://{SPEC.alarmapi_user}:{SPEC.alarmapi_password}@{host}:{port}/{SPEC.alarmdb}"
    engine = create_engine(dsn)
    metadata.drop_all(engine)
    metadata.create_all(engine)
    return engine


def test_all_seven_tables_exist(alarmdb_engine: Engine) -> None:
    inspector_tables = set(inspect(alarmdb_engine).get_table_names())
    assert inspector_tables == {
        "sites",
        "units",
        "assets",
        "alarm_definitions",
        "alarms",
        "kpi_definitions",
        "calculation_runs",
    }


def test_insert_and_query_site_unit_asset(alarmdb_engine: Engine) -> None:
    with alarmdb_engine.begin() as conn:
        conn.execute(insert(sites).values(name="NorthPlant"))
        conn.execute(
            insert(units).values(
                name="Unit 1", site="NorthPlant", operator_console_id="NP-U1-CONSOLE"
            )
        )
        conn.execute(
            insert(assets).values(
                asset_id="NP-U1-BFP-101",
                asset_name="Boiler Feed Pump 101",
                asset_type="pump",
                site="NorthPlant",
                unit="Unit 1",
                criticality="high",
            )
        )
    with alarmdb_engine.connect() as conn:
        row = conn.execute(select(assets).where(assets.c.asset_id == "NP-U1-BFP-101")).one()
        assert row.asset_name == "Boiler Feed Pump 101"


def test_asset_type_check_constraint_rejects_invalid_value(alarmdb_engine: Engine) -> None:
    with pytest.raises((IntegrityError, DataError)), alarmdb_engine.begin() as conn:
        conn.execute(
            insert(assets).values(
                asset_id="BAD-1",
                asset_name="Bad Asset",
                asset_type="spaceship",
                site="NorthPlant",
                unit="Unit 1",
                criticality="high",
            )
        )


def test_alarm_definition_and_alarm_roundtrip(alarmdb_engine: Engine) -> None:
    with alarmdb_engine.begin() as conn:
        conn.execute(
            insert(alarm_definitions).values(
                alarm_code="BFP101-VIB-HH",
                asset_id="NP-U1-BFP-101",
                alarm_name="Vibration High-High",
                alarm_type="process",
                severity="high",
                is_sif_related=False,
                safety_classification="none",
                cause="Bearing wear",
                consequence="Pump trip",
                corrective_action="Inspect bearing",
                allowable_response_time_s=600,
            )
        )
        conn.execute(
            insert(alarms).values(
                alarm_id="ALM-2026-000001",
                alarm_code="BFP101-VIB-HH",
                asset_id="NP-U1-BFP-101",
                asset_name="Boiler Feed Pump 101",
                site="NorthPlant",
                unit="Unit 1",
                alarm_name="Vibration High-High",
                alarm_type="process",
                severity="high",
                is_sif_related=False,
                start_time=datetime(2026, 5, 1, tzinfo=UTC),
                status="cleared",
            )
        )
    with alarmdb_engine.connect() as conn:
        row = conn.execute(select(alarms).where(alarms.c.alarm_id == "ALM-2026-000001")).one()
        assert row.alarm_code == "BFP101-VIB-HH"


def test_alarm_rejects_unknown_alarm_code(alarmdb_engine: Engine) -> None:
    with pytest.raises(IntegrityError), alarmdb_engine.begin() as conn:
        conn.execute(
            insert(alarms).values(
                alarm_id="ALM-2026-999999",
                alarm_code="DOES-NOT-EXIST",
                asset_id="NP-U1-BFP-101",
                asset_name="Boiler Feed Pump 101",
                site="NorthPlant",
                unit="Unit 1",
                alarm_name="x",
                alarm_type="process",
                severity="high",
                is_sif_related=False,
                start_time=datetime(2026, 5, 1, tzinfo=UTC),
                status="cleared",
            )
        )


def test_kpi_definitions_and_calculation_runs_roundtrip(alarmdb_engine: Engine) -> None:
    with alarmdb_engine.begin() as conn:
        conn.execute(
            insert(kpi_definitions).values(
                kpi_id="nuisance_alarm_score",
                name="Nuisance Alarm Score",
                description="Composite nuisance score 0-100",
                formula="freq*0.4 + chatter*0.25 + fleeting*0.2 + unacked*0.15",
                unit="score",
                reference="EEMUA 191",
            )
        )
        conn.execute(
            insert(calculation_runs).values(
                calculation_id="calc-001",
                calculation_type="nuisance_alarm_score",
                generated_code="def run(): ...",
                status="completed",
                created_at=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
    with alarmdb_engine.connect() as conn:
        kpi = conn.execute(
            select(kpi_definitions).where(kpi_definitions.c.kpi_id == "nuisance_alarm_score")
        ).one()
        assert kpi.reference == "EEMUA 191"
        run = conn.execute(
            select(calculation_runs).where(calculation_runs.c.calculation_id == "calc-001")
        ).one()
        assert run.status == "completed"
