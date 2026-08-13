"""alarmdb schema (06-data-model.md §3). Occurrence-based alarm model: `alarms.alarm_id`
is one activation-to-clear occurrence; `alarm_definitions.alarm_code` is the recurring
condition -- the unit of rationalization. CHECK constraints mirror the enumerations in
01-architecture.md §3 so invalid data is rejected by the database, not just by the API.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

sites = Table(
    "sites",
    metadata,
    Column("name", String, primary_key=True),
)

units = Table(
    "units",
    metadata,
    Column("name", String, primary_key=True),
    Column("site", String, ForeignKey("sites.name"), nullable=False),
    Column("operator_console_id", String, nullable=True),
)

assets = Table(
    "assets",
    metadata,
    Column("asset_id", String, primary_key=True),
    Column("asset_name", String, nullable=False),
    Column("asset_type", String, nullable=False),
    Column("site", String, nullable=False),
    Column("unit", String, nullable=False),
    Column("criticality", String, nullable=False),
    Column("service_description", Text, nullable=True),
    Column("manufacturer", String, nullable=True),
    Column("model", String, nullable=True),
    Column("install_date", Date, nullable=True),
    Column("parent_asset_id", String, ForeignKey("assets.asset_id"), nullable=True),
    Column("tag_prefix", String, nullable=True),
    CheckConstraint(
        "asset_type IN ('pump','compressor','motor','valve','exchanger','turbine')",
        name="ck_assets_asset_type",
    ),
    CheckConstraint(
        "criticality IN ('low','medium','high','critical')", name="ck_assets_criticality"
    ),
)

alarm_definitions = Table(
    "alarm_definitions",
    metadata,
    Column("alarm_code", String, primary_key=True),
    Column("asset_id", String, ForeignKey("assets.asset_id"), nullable=False),
    Column("alarm_name", String, nullable=False),
    Column("alarm_type", String, nullable=False),
    Column("severity", String, nullable=False),
    Column("measurement", String, nullable=True),
    Column("unit_of_measure", String, nullable=True),
    Column("setpoint", Float, nullable=True),
    Column("deadband", Float, nullable=True),
    Column("on_delay_s", Float, nullable=True),
    Column("is_sif_related", Boolean, nullable=False, server_default="false"),
    Column("safety_classification", String, nullable=False, server_default="none"),
    Column("sif_tag", String, nullable=True),
    Column("cause", Text, nullable=False),
    Column("consequence", Text, nullable=False),
    Column("corrective_action", Text, nullable=False),
    Column("allowable_response_time_s", Float, nullable=False),
    Column("is_suppressed", Boolean, nullable=False, server_default="false"),
    Column("suppression_reason", Text, nullable=True),
    CheckConstraint(
        "alarm_type IN ('safety','device','process','deviation')", name="ck_alarmdef_alarm_type"
    ),
    CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_alarmdef_severity"),
    CheckConstraint(
        "safety_classification IN ('none','sif','hazard_protection','regulatory')",
        name="ck_alarmdef_safety_classification",
    ),
)

alarms = Table(
    "alarms",
    metadata,
    Column("alarm_id", String, primary_key=True),
    Column("alarm_code", String, ForeignKey("alarm_definitions.alarm_code"), nullable=False),
    Column("asset_id", String, ForeignKey("assets.asset_id"), nullable=False),
    Column("asset_name", String, nullable=False),
    Column("site", String, nullable=False),
    Column("unit", String, nullable=False),
    Column("alarm_name", String, nullable=False),
    Column("alarm_type", String, nullable=False),
    Column("severity", String, nullable=False),
    Column("is_sif_related", Boolean, nullable=False, server_default="false"),
    Column("start_time", DateTime(timezone=True), nullable=False),
    Column("end_time", DateTime(timezone=True), nullable=True),
    Column("ack_time", DateTime(timezone=True), nullable=True),
    Column("status", String, nullable=False),
    Column("duration_s", Float, nullable=True),
    Column("ack_delay_s", Float, nullable=True),
    Column("value_at_activation", Float, nullable=True),
    Column("setpoint", Float, nullable=True),
    Column("operator_id", String, nullable=True),
    CheckConstraint(
        "status IN ('active','acknowledged','cleared','shelved','suppressed')",
        name="ck_alarms_status",
    ),
    CheckConstraint(
        "alarm_type IN ('safety','device','process','deviation')", name="ck_alarms_alarm_type"
    ),
    CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_alarms_severity"),
    Index("ix_alarms_asset_start", "asset_id", "start_time"),
    Index("ix_alarms_unit_start", "unit", "start_time"),
    Index("ix_alarms_site_status", "site", "status"),
    Index("ix_alarms_code_start", "alarm_code", "start_time"),
    Index("ix_alarms_start", "start_time"),
)

kpi_definitions = Table(
    "kpi_definitions",
    metadata,
    Column("kpi_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=False),
    Column("formula", Text, nullable=False),
    Column("unit", String, nullable=True),
    Column("reference", String, nullable=True),
)

calculation_runs = Table(
    "calculation_runs",
    metadata,
    Column("calculation_id", String, primary_key=True),
    Column("calculation_type", String, nullable=False),
    Column("filters_json", JSON, nullable=True),
    Column("generated_code", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("result_json", JSON, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("executed_at", DateTime(timezone=True), nullable=True),
    Column("duration_ms", Float, nullable=True),
)
