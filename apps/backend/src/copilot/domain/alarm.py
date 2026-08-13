"""Alarm domain vocabulary: enums, TimeRange, and the occurrence-based Alarm record.

Terminology follows ISA-18.2 / EEMUA 191 as adapted in 06-data-model.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AlarmSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlarmStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"
    SHELVED = "shelved"
    SUPPRESSED = "suppressed"


class AlarmType(StrEnum):
    SAFETY = "safety"
    DEVICE = "device"
    PROCESS = "process"
    DEVIATION = "deviation"


class SafetyClassification(StrEnum):
    NONE = "none"
    SIF = "sif"
    HAZARD_PROTECTION = "hazard_protection"
    REGULATORY = "regulatory"


class TimeRange(BaseModel):
    """An inclusive-exclusive query window. start_time must precede end_time."""

    model_config = ConfigDict(frozen=True)

    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def _check_ordering(self) -> TimeRange:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be strictly before end_time")
        return self


class Alarm(BaseModel):
    """One alarm occurrence: activation through clear. `alarm_code` identifies the
    recurring condition; `alarm_id` identifies this one instance of it.
    """

    model_config = ConfigDict(frozen=True)

    alarm_id: str
    alarm_code: str
    asset_id: str
    asset_name: str
    site: str
    unit: str
    alarm_name: str
    alarm_type: AlarmType
    severity: AlarmSeverity
    is_sif_related: bool
    safety_classification: SafetyClassification
    start_time: datetime
    end_time: datetime | None = None
    ack_time: datetime | None = None
    status: AlarmStatus
    duration_s: float | None = Field(default=None, ge=0)
    ack_delay_s: float | None = Field(default=None, ge=0)
    value_at_activation: float | None = None
    setpoint: float | None = None
    operator_id: str | None = None

    @model_validator(mode="after")
    def _check_end_after_start(self) -> Alarm:
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError("end_time must not precede start_time")
        return self

    @model_validator(mode="after")
    def _check_sif_consistency(self) -> Alarm:
        if self.is_sif_related and self.safety_classification is SafetyClassification.NONE:
            raise ValueError(
                "is_sif_related=True requires a non-NONE safety_classification "
                "(the SIF gate depends on this pair never drifting apart)"
            )
        return self
