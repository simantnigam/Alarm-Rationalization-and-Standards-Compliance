"""Typed MCP tool I/O schemas. Distinct from connectors.alarm_api.models: this is the
MCP-level contract exposed to the copilot, not the wire contract with the Alarm API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AssetResult(BaseModel):
    asset_id: str
    asset_name: str
    asset_type: str
    site: str
    unit: str
    criticality: str


class SearchAssetsOutput(BaseModel):
    results: list[AssetResult]
    total: int
    # Echoes the Alarm API simulator's own echoed trace_id (from its response `meta`
    # block), so trace propagation end to end -- GUI -> copilot -> MCP _meta -> HTTP
    # header -> simulator -> response -> here -- is assertable in one field, not just
    # claimed (01-architecture.md §3).
    simulator_trace_id: str | None = None


class AlarmResult(BaseModel):
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


class ListAlarmsOutput(BaseModel):
    alarms: list[AlarmResult]
    total: int
    # True when the hard page cap was hit before the upstream ran out of pages --
    # 01-architecture.md §5.1's "auto-paginate, capped" surfaced, never a silent
    # truncation (mirrors connectors.alarm_api.client.paginate_alarms's own log signal).
    truncated: bool
    simulator_trace_id: str | None = None


class SummaryGroupResult(BaseModel):
    key: dict[str, str]
    kpis: dict[str, float]


class GetAlarmSummaryOutput(BaseModel):
    groups: list[SummaryGroupResult]
    totals: dict[str, float]
    time_range: dict[str, str] | None = None
    simulator_trace_id: str | None = None


class TrendPointResult(BaseModel):
    bucket_start: str
    value: float


class TrendSeriesResult(BaseModel):
    metric: str
    points: list[TrendPointResult]


class GetAlarmTrendsOutput(BaseModel):
    bucket: str
    series: list[TrendSeriesResult]
    time_range: dict[str, str] | None = None
    simulator_trace_id: str | None = None


class FloodContributorResult(BaseModel):
    alarm_code: str
    count: int


class FloodWindowResult(BaseModel):
    start: str
    end: str
    unit: str | None = None
    alarm_count: int
    peak_rate_per_10min: int
    top_contributors: list[FloodContributorResult]


class AnalyzeAlarmFloodOutput(BaseModel):
    flood_windows: list[FloodWindowResult]
    threshold_count: int
    rolling_window_minutes: float
    total_flood_minutes: float
    simulator_trace_id: str | None = None


class RationalizationCandidateResult(BaseModel):
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


class GetRationalizationCandidatesOutput(BaseModel):
    candidates: list[RationalizationCandidateResult]
    total: int
    thresholds: dict[str, float] | None = None
    time_range: dict[str, str] | None = None
    simulator_trace_id: str | None = None


class CorrelationPairResult(BaseModel):
    alarm_code_a: str
    alarm_code_b: str
    asset_a: str
    asset_b: str
    cooccurrence_count: int
    support: float
    confidence: float
    avg_lag_seconds: float
    direction: str


class CorrelateAlarmsOutput(BaseModel):
    pairs: list[CorrelationPairResult]
    method: str
    params: dict[str, object]
    simulator_trace_id: str | None = None


class RationalizationRecordResult(BaseModel):
    cause: str
    consequence: str
    corrective_action: str
    allowable_response_time_s: float


class GetOperatorRecommendationsOutput(BaseModel):
    alarm_id: str
    alarm_code: str
    immediate_actions: list[str]
    diagnostic_steps: list[str]
    rationalization_record: RationalizationRecordResult
    asset_context: dict[str, object] | None = None
    related_alarms: list[dict[str, object]] | None = None
    historical_pattern: dict[str, object] | None = None
    simulator_trace_id: str | None = None


class GenerateKpiCalculationOutput(BaseModel):
    calculation_id: str
    calculation_type: str
    code: str
    language: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    created_at: str
    simulator_trace_id: str | None = None


class ExecuteKpiCalculationOutput(BaseModel):
    calculation_id: str
    calculation_type: str
    status: str
    result: dict[str, object]
    row_count: int
    duration_ms: float
    executed_at: str
    simulator_trace_id: str | None = None
