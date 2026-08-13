"""Typed response models for the Alarm Management API. Deliberately independent of
copilot.domain -- this connector models an external system's wire contract, which is
a different concern from the copilot's own shared vocabulary (01-architecture.md §6).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str | None = None
    trace_id: str | None = None
    client_id: str | None = None
    metadata_tag: str | None = None
    generated_at: str | None = None
    duration_ms: float | None = None
    sim_profile: str | None = None


class Asset(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: str
    asset_name: str
    asset_type: str
    site: str
    unit: str
    criticality: str
    service_description: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    install_date: date | None = None
    parent_asset_id: str | None = None
    tag_prefix: str | None = None


class AssetSearchResponse(BaseModel):
    results: list[Asset]
    total: int
    query: str
    limit: int
    meta: ResponseMeta


class Alarm(BaseModel):
    model_config = ConfigDict(extra="allow")

    alarm_id: str
    alarm_code: str
    asset_id: str
    asset_name: str
    site: str
    unit: str
    alarm_name: str
    alarm_type: str
    severity: str
    is_sif_related: bool
    start_time: datetime
    end_time: datetime | None = None
    ack_time: datetime | None = None
    status: str
    duration_s: float | None = None
    ack_delay_s: float | None = None
    value_at_activation: float | None = None
    setpoint: float | None = None
    operator_id: str | None = None


class AlarmListResponse(BaseModel):
    data: list[Alarm]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_more: bool
    sort_by: str
    sort_order: str
    meta: ResponseMeta


class SummaryGroup(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: dict[str, str]
    kpis: dict[str, float]


class SummaryResponse(BaseModel):
    groups: list[SummaryGroup]
    totals: dict[str, float]
    time_range: dict[str, str] | None = None
    meta: ResponseMeta


class TrendPoint(BaseModel):
    bucket_start: str
    value: float


class TrendSeries(BaseModel):
    metric: str
    points: list[TrendPoint]


class TrendsResponse(BaseModel):
    bucket: str
    series: list[TrendSeries]
    time_range: dict[str, str] | None = None
    meta: ResponseMeta


class CorrelationPair(BaseModel):
    model_config = ConfigDict(extra="allow")

    alarm_code_a: str
    alarm_code_b: str
    asset_a: str
    asset_b: str
    cooccurrence_count: int
    support: float
    confidence: float
    avg_lag_seconds: float
    direction: str


class CorrelationResponse(BaseModel):
    pairs: list[CorrelationPair]
    method: str
    params: dict[str, object]
    meta: ResponseMeta


class FloodContributor(BaseModel):
    alarm_code: str
    count: int


class FloodWindow(BaseModel):
    start: str
    end: str
    unit: str | None = None
    alarm_count: int
    peak_rate_per_10min: int
    top_contributors: list[FloodContributor]


class FloodAnalysisResponse(BaseModel):
    flood_windows: list[FloodWindow]
    threshold_count: int
    rolling_window_minutes: float
    total_flood_minutes: float
    meta: ResponseMeta


class RationalizationCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    alarm_code: str
    asset_id: str
    asset_name: str
    site: str
    unit: str
    severity: str
    is_sif_related: bool
    safety_classification: str
    occurrences: int
    occurrences_90d: int
    occurrences_per_day: float
    stale_occurrences: int
    max_stale_minutes: float
    chatter_index: int
    fleeting_count: int
    fleeting_rate: float
    avg_ack_delay_s: float
    max_ack_delay_s: float
    unacknowledged_rate: float
    nuisance_score: float
    category: str
    reason: str


class CandidatesResponse(BaseModel):
    candidates: list[RationalizationCandidate]
    total: int
    thresholds: dict[str, float] | None = None
    time_range: dict[str, str] | None = None
    meta: ResponseMeta


class RationalizationRecord(BaseModel):
    cause: str
    consequence: str
    corrective_action: str
    allowable_response_time_s: float


class OperatorRecommendationsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    alarm_id: str
    alarm_code: str
    immediate_actions: list[str]
    diagnostic_steps: list[str]
    rationalization_record: RationalizationRecord
    asset_context: dict[str, object] | None = None
    related_alarms: list[dict[str, object]] | None = None
    historical_pattern: dict[str, object] | None = None
    meta: ResponseMeta


class GenerateCalculationResponse(BaseModel):
    calculation_id: str
    calculation_type: str
    code: str
    language: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    created_at: str
    meta: ResponseMeta


class ExecuteCalculationResponse(BaseModel):
    calculation_id: str
    calculation_type: str
    status: str
    result: dict[str, object]
    row_count: int
    duration_ms: float
    executed_at: str
    meta: ResponseMeta
