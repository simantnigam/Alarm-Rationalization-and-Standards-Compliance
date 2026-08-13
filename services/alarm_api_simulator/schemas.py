"""Request bodies for the POST analytics endpoints. Request shapes are pinned exactly
by the Postman collections where given; fields absent from every supplied request stay
optional with documented defaults.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
AlarmType = Literal["safety", "device", "process", "deviation"]
GroupByField = Literal["alarm_name", "asset_id", "asset_name", "severity", "alarm_code"]


class TimeRangeIn(BaseModel):
    start_time: datetime
    end_time: datetime


class ScopeFilter(BaseModel):
    asset_ids: list[str] | None = None
    unit: str | None = None
    site: str | None = None
    time_range: TimeRangeIn | None = None


class SummaryRequest(ScopeFilter):
    severity: list[Severity] | None = None
    alarm_types: list[AlarmType] | None = None
    group_by: list[GroupByField] = Field(default_factory=list)
    kpis: list[str] | None = None


class TrendsRequest(ScopeFilter):
    bucket: Literal["hourly", "daily", "weekly", "monthly"] = "daily"
    metrics: list[str] = Field(default_factory=lambda: ["alarm_count"])


class CorrelationRequest(ScopeFilter):
    correlation_method: Literal["cooccurrence"] = "cooccurrence"
    lag_window_minutes: float = Field(default=15, gt=0)
    severity_threshold: Severity = "medium"
    min_support: int = Field(default=1, ge=1)


class FloodRequest(BaseModel):
    unit: str | None = None
    site: str | None = None
    time_range: TimeRangeIn | None = None
    threshold_count: int = Field(default=10, ge=1)
    rolling_window_minutes: float = Field(default=10, gt=0)


class CandidatesRequest(ScopeFilter):
    recurrence_threshold: int = Field(default=25, ge=1)
    stale_minutes_threshold: float = Field(default=1440, gt=0)


class PriorityScoreRequest(BaseModel):
    alarm_id: str


class OperatorActionsRequest(BaseModel):
    alarm_id: str
    include_related: bool = False
    include_asset_context: bool = False
    include_historical_pattern: bool = False


CalculationType = Literal[
    "alarm_flood_index",
    "critical_alarm_density",
    "operator_response_efficiency",
    "nuisance_alarm_score",
]


class CalculationFilters(BaseModel):
    unit: str | None = None
    site: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class GenerateCalculationRequest(BaseModel):
    # A server-side allowlist (Literal), not a free-form string -- the LLM chooses which
    # registered calculation to run, it never authors what executes (4.5.3x).
    calculation_type: CalculationType
    filters: CalculationFilters = Field(default_factory=CalculationFilters)


class ExecuteCalculationRequest(BaseModel):
    calculation_id: str
    filters: CalculationFilters = Field(default_factory=CalculationFilters)
