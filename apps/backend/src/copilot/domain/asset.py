"""Asset, Site, and Unit -- the plant topology alarms and rationalization candidates
are scoped against.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AssetType(StrEnum):
    PUMP = "pump"
    COMPRESSOR = "compressor"
    MOTOR = "motor"
    VALVE = "valve"
    EXCHANGER = "exchanger"
    TURBINE = "turbine"


class Criticality(StrEnum):
    """Deliberately distinct from AlarmSeverity even though the string values coincide:
    an asset's criticality and an alarm's severity are independent concepts and must
    never be silently interchangeable.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Site(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)


class Unit(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    site: str = Field(min_length=1)
    operator_console_id: str | None = None


class Asset(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    asset_name: str
    asset_type: AssetType
    site: str
    unit: str
    criticality: Criticality
    service_description: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    install_date: date | None = None
    parent_asset_id: str | None = None
    tag_prefix: str | None = None
