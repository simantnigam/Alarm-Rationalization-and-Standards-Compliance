"""alarm-management MCP server: the 10 read tools scoped for 02-phases.md Phase 4 (the
2 write-path tools -- preview_rationalization_decision, submit_rationalization_decision
-- stay in Phase 9, per 04-scope-lock.md C-1). Every tool calls the real connector
(connectors.alarm_api.client.AlarmApiClient); AlarmApiError is mapped through
mcp_servers.alarm_management.errors.map_error into the 01-architecture.md §5.1 7-row
error table before it ever reaches a CallToolResult.
"""

from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from connectors.alarm_api.client import AlarmApiClient
from connectors.alarm_api.errors import AlarmApiError
from connectors.alarm_api.models import (
    Alarm,
    CorrelationPair,
    FloodWindow,
    RationalizationCandidate,
    RationalizationRecord,
    SummaryGroup,
    TrendSeries,
)
from connectors.alarm_api.trace import TraceContext
from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.errors import map_error
from mcp_servers.alarm_management.schemas import (
    AlarmResult,
    AnalyzeAlarmFloodOutput,
    AssetResult,
    CorrelateAlarmsOutput,
    CorrelationPairResult,
    ExecuteKpiCalculationOutput,
    FloodContributorResult,
    FloodWindowResult,
    GenerateKpiCalculationOutput,
    GetAlarmSummaryOutput,
    GetAlarmTrendsOutput,
    GetOperatorRecommendationsOutput,
    GetRationalizationCandidatesOutput,
    ListAlarmsOutput,
    RationalizationCandidateResult,
    RationalizationRecordResult,
    SearchAssetsOutput,
    SummaryGroupResult,
    TrendPointResult,
    TrendSeriesResult,
)

# GET /alarms (auto-paginate, capped) -- a tool-layer policy, not a connector one, so the
# hard cap can be turned into the queryable `truncated` output field instead of only a
# log line (contrast connectors.alarm_api.client.paginate_alarms, which logs and stops).
_LIST_ALARMS_PAGE_SIZE = 50
_LIST_ALARMS_MAX_PAGES = 20


def _trace_id_from(ctx: Context) -> str | None:
    """Correlation/trace metadata propagates via the MCP request's `_meta` field (the
    client sends `meta={"trace_id": ...}` on call_tool), not as a tool argument -- so it
    never appears in the tool's public input schema.
    """
    meta = ctx.request_context.meta
    return getattr(meta, "trace_id", None) if meta else None


def _alarm_result(a: Alarm) -> AlarmResult:
    return AlarmResult(
        alarm_id=a.alarm_id,
        alarm_code=a.alarm_code,
        asset_id=a.asset_id,
        asset_name=a.asset_name,
        site=a.site,
        unit=a.unit,
        alarm_name=a.alarm_name,
        alarm_type=a.alarm_type,
        severity=a.severity,
        is_sif_related=a.is_sif_related,
        start_time=a.start_time,
        end_time=a.end_time,
        ack_time=a.ack_time,
        status=a.status,
        duration_s=a.duration_s,
        ack_delay_s=a.ack_delay_s,
        value_at_activation=a.value_at_activation,
        setpoint=a.setpoint,
        operator_id=a.operator_id,
    )


def _summary_group_result(g: SummaryGroup) -> SummaryGroupResult:
    return SummaryGroupResult(key=g.key, kpis=g.kpis)


def _trend_series_result(s: TrendSeries) -> TrendSeriesResult:
    return TrendSeriesResult(
        metric=s.metric,
        points=[TrendPointResult(bucket_start=p.bucket_start, value=p.value) for p in s.points],
    )


def _flood_window_result(w: FloodWindow) -> FloodWindowResult:
    return FloodWindowResult(
        start=w.start,
        end=w.end,
        unit=w.unit,
        alarm_count=w.alarm_count,
        peak_rate_per_10min=w.peak_rate_per_10min,
        top_contributors=[
            FloodContributorResult(alarm_code=c.alarm_code, count=c.count)
            for c in w.top_contributors
        ],
    )


def _candidate_result(c: RationalizationCandidate) -> RationalizationCandidateResult:
    return RationalizationCandidateResult(
        alarm_code=c.alarm_code,
        asset_id=c.asset_id,
        asset_name=c.asset_name,
        site=c.site,
        unit=c.unit,
        severity=c.severity,
        is_sif_related=c.is_sif_related,
        safety_classification=c.safety_classification,
        occurrences=c.occurrences,
        occurrences_90d=c.occurrences_90d,
        occurrences_per_day=c.occurrences_per_day,
        stale_occurrences=c.stale_occurrences,
        max_stale_minutes=c.max_stale_minutes,
        chatter_index=c.chatter_index,
        fleeting_count=c.fleeting_count,
        fleeting_rate=c.fleeting_rate,
        avg_ack_delay_s=c.avg_ack_delay_s,
        max_ack_delay_s=c.max_ack_delay_s,
        unacknowledged_rate=c.unacknowledged_rate,
        nuisance_score=c.nuisance_score,
        category=c.category,
        reason=c.reason,
    )


def _correlation_pair_result(p: CorrelationPair) -> CorrelationPairResult:
    return CorrelationPairResult(
        alarm_code_a=p.alarm_code_a,
        alarm_code_b=p.alarm_code_b,
        asset_a=p.asset_a,
        asset_b=p.asset_b,
        cooccurrence_count=p.cooccurrence_count,
        support=p.support,
        confidence=p.confidence,
        avg_lag_seconds=p.avg_lag_seconds,
        direction=p.direction,
    )


def _rationalization_record_result(r: RationalizationRecord) -> RationalizationRecordResult:
    return RationalizationRecordResult(
        cause=r.cause,
        consequence=r.consequence,
        corrective_action=r.corrective_action,
        allowable_response_time_s=r.allowable_response_time_s,
    )


def build_server(settings: AlarmMcpSettings, *, client: AlarmApiClient | None = None) -> FastMCP:
    # DNS-rebinding protection is a browser-threat mitigation (a malicious webpage
    # tricking a victim's browser into hitting a localhost service); it doesn't apply
    # to this server-to-server MCP connection, but the correct response is an accurate
    # allowlist, not disabling the check.
    mcp = FastMCP(
        name="alarm-management",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_hosts_list,
            allowed_origins=settings.allowed_hosts_list,
        ),
    )
    client = client or AlarmApiClient(
        base_url=settings.alarm_api_base_url, token=settings.alarm_api_token
    )

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @mcp.tool(
        name="search_assets",
        description=(
            "Search for plant assets (pumps, compressors, motors, valves, exchangers, "
            "turbines) by name, type, or location. Use this to resolve an asset name "
            "mentioned in a question (e.g. 'Boiler Feed Pump 101') into an asset_id "
            "before calling other tools."
        ),
    )
    async def search_assets(
        ctx: Context,
        query: str,
        limit: int = 20,
        unit: str | None = None,
        site: str | None = None,
    ) -> SearchAssetsOutput:
        try:
            response = await client.search_assets(
                query=query,
                limit=limit,
                unit=unit,
                site=site,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return SearchAssetsOutput(
            results=[
                AssetResult(
                    asset_id=a.asset_id,
                    asset_name=a.asset_name,
                    asset_type=a.asset_type,
                    site=a.site,
                    unit=a.unit,
                    criticality=a.criticality,
                )
                for a in response.results
            ],
            total=response.total,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="list_alarms",
        description=(
            "List alarms matching filters (asset, unit, site, status, time range). "
            "Automatically paginates through all matching results up to an internal "
            "cap -- check `truncated` in the response to know whether more alarms "
            "exist beyond it. Use this to inspect specific alarm events, not aggregate "
            "statistics (use get_alarm_summary or get_alarm_trends for that)."
        ),
    )
    async def list_alarms(
        ctx: Context,
        asset_id: str | None = None,
        unit: str | None = None,
        site: str | None = None,
        status: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        sort_by: str = "start_time",
        sort_order: str = "desc",
    ) -> ListAlarmsOutput:
        trace = TraceContext(trace_id=_trace_id_from(ctx))
        alarms: list[AlarmResult] = []
        simulator_trace_id: str | None = None
        truncated = False
        page = 1
        try:
            while True:
                response = await client.list_alarms(
                    asset_id=asset_id,
                    unit=unit,
                    site=site,
                    status=status,
                    start_time=start_time,
                    end_time=end_time,
                    page=page,
                    page_size=_LIST_ALARMS_PAGE_SIZE,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    trace=trace,
                )
                alarms.extend(_alarm_result(a) for a in response.data)
                simulator_trace_id = response.meta.trace_id
                if not response.has_more:
                    break
                if page >= _LIST_ALARMS_MAX_PAGES:
                    truncated = True
                    break
                page += 1
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return ListAlarmsOutput(
            alarms=alarms,
            total=len(alarms),
            truncated=truncated,
            simulator_trace_id=simulator_trace_id,
        )

    @mcp.tool(
        name="get_alarm_summary",
        description=(
            "Compute grouped alarm KPI totals (e.g. alarm_count, recurring_rate, "
            "avg_ack_delay) over a time range, optionally grouped by asset, "
            "alarm_name, severity, etc. Use this for aggregate counts and rates "
            "instead of listing individual alarms."
        ),
    )
    async def get_alarm_summary(
        ctx: Context,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        severity: list[str] | None = None,
        alarm_types: list[str] | None = None,
        group_by: list[str] | None = None,
        kpis: list[str] | None = None,
    ) -> GetAlarmSummaryOutput:
        try:
            response = await client.get_alarm_summary(
                asset_ids=asset_ids,
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                severity=severity,
                alarm_types=alarm_types,
                group_by=group_by,
                kpis=kpis,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return GetAlarmSummaryOutput(
            groups=[_summary_group_result(g) for g in response.groups],
            totals=response.totals,
            time_range=response.time_range,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="get_alarm_trends",
        description=(
            "Compute time-bucketed KPI trend series (e.g. daily alarm_count) over a "
            "time range. Use this to see how a metric changes over time, not a single "
            "aggregate total."
        ),
    )
    async def get_alarm_trends(
        ctx: Context,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        bucket: str = "daily",
        metrics: list[str] | None = None,
    ) -> GetAlarmTrendsOutput:
        try:
            response = await client.get_alarm_trends(
                asset_ids=asset_ids,
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                bucket=bucket,
                metrics=metrics,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return GetAlarmTrendsOutput(
            bucket=response.bucket,
            series=[_trend_series_result(s) for s in response.series],
            time_range=response.time_range,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="analyze_alarm_flood",
        description=(
            "Detect alarm flood windows (periods where the alarm rate exceeds a "
            "threshold) over a time range. Use this to find operator-overload "
            "periods, per ISA-18.2 flood criteria."
        ),
    )
    async def analyze_alarm_flood(
        ctx: Context,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        threshold_count: int = 10,
        rolling_window_minutes: float = 10,
    ) -> AnalyzeAlarmFloodOutput:
        try:
            response = await client.analyze_alarm_flood(
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                threshold_count=threshold_count,
                rolling_window_minutes=rolling_window_minutes,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return AnalyzeAlarmFloodOutput(
            flood_windows=[_flood_window_result(w) for w in response.flood_windows],
            threshold_count=response.threshold_count,
            rolling_window_minutes=response.rolling_window_minutes,
            total_flood_minutes=response.total_flood_minutes,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="get_rationalization_candidates",
        description=(
            "Identify alarms that are candidates for rationalization (stale, "
            "recurring, nuisance, chattering, fleeting) based on configurable "
            "thresholds. Use this as the starting point for an alarm rationalization "
            "review."
        ),
    )
    async def get_rationalization_candidates(
        ctx: Context,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        recurrence_threshold: int = 25,
        stale_minutes_threshold: float = 1440,
    ) -> GetRationalizationCandidatesOutput:
        try:
            response = await client.get_rationalization_candidates(
                asset_ids=asset_ids,
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                recurrence_threshold=recurrence_threshold,
                stale_minutes_threshold=stale_minutes_threshold,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return GetRationalizationCandidatesOutput(
            candidates=[_candidate_result(c) for c in response.candidates],
            total=response.total,
            thresholds=response.thresholds,
            time_range=response.time_range,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="correlate_alarms",
        description=(
            "Find alarm pairs that co-occur or are otherwise correlated across a set "
            "of assets, using a configurable correlation method and lag window. Use "
            "this to spot alarms that tend to fire together, a signal of a shared "
            "root cause."
        ),
    )
    async def correlate_alarms(
        ctx: Context,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        correlation_method: str = "cooccurrence",
        lag_window_minutes: float = 15,
        severity_threshold: str = "medium",
        min_support: int = 1,
    ) -> CorrelateAlarmsOutput:
        try:
            response = await client.correlate_alarms(
                asset_ids=asset_ids,
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                correlation_method=correlation_method,
                lag_window_minutes=lag_window_minutes,
                severity_threshold=severity_threshold,
                min_support=min_support,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return CorrelateAlarmsOutput(
            pairs=[_correlation_pair_result(p) for p in response.pairs],
            method=response.method,
            params=response.params,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="get_operator_recommendations",
        description=(
            "Get the recommended immediate actions, diagnostic steps, and "
            "rationalization record (cause/consequence/corrective action) for a "
            "specific alarm. Use this after search_assets/list_alarms has resolved a "
            "specific alarm_id."
        ),
    )
    async def get_operator_recommendations(
        ctx: Context,
        alarm_id: str,
        include_related: bool = False,
        include_asset_context: bool = False,
        include_historical_pattern: bool = False,
    ) -> GetOperatorRecommendationsOutput:
        try:
            response = await client.get_operator_recommendations(
                alarm_id=alarm_id,
                include_related=include_related,
                include_asset_context=include_asset_context,
                include_historical_pattern=include_historical_pattern,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return GetOperatorRecommendationsOutput(
            alarm_id=response.alarm_id,
            alarm_code=response.alarm_code,
            immediate_actions=response.immediate_actions,
            diagnostic_steps=response.diagnostic_steps,
            rationalization_record=_rationalization_record_result(response.rationalization_record),
            asset_context=response.asset_context,
            related_alarms=response.related_alarms,
            historical_pattern=response.historical_pattern,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="generate_kpi_calculation",
        description=(
            "Generate the code for a registered KPI calculation type over a "
            "scope/time range, returning a calculation_id and the code to review "
            "before execution. Use this before execute_kpi_calculation -- the "
            "copilot may never submit its own calculation code, only run a "
            "previously generated one."
        ),
    )
    async def generate_kpi_calculation(
        ctx: Context,
        calculation_type: str,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> GenerateKpiCalculationOutput:
        try:
            response = await client.generate_kpi_calculation(
                calculation_type=calculation_type,
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return GenerateKpiCalculationOutput(
            calculation_id=response.calculation_id,
            calculation_type=response.calculation_type,
            code=response.code,
            language=response.language,
            description=response.description,
            input_schema=response.input_schema,
            output_schema=response.output_schema,
            created_at=response.created_at,
            simulator_trace_id=response.meta.trace_id,
        )

    @mcp.tool(
        name="execute_kpi_calculation",
        description=(
            "Execute a previously generated KPI calculation by its calculation_id, "
            "returning the computed result. Requires calling "
            "generate_kpi_calculation first to obtain the calculation_id."
        ),
    )
    async def execute_kpi_calculation(
        ctx: Context,
        calculation_id: str,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ExecuteKpiCalculationOutput:
        try:
            response = await client.execute_kpi_calculation(
                calculation_id=calculation_id,
                unit=unit,
                site=site,
                start_time=start_time,
                end_time=end_time,
                trace=TraceContext(trace_id=_trace_id_from(ctx)),
            )
        except AlarmApiError as exc:
            raise map_error(exc) from exc

        return ExecuteKpiCalculationOutput(
            calculation_id=response.calculation_id,
            calculation_type=response.calculation_type,
            status=response.status,
            result=response.result,
            row_count=response.row_count,
            duration_ms=response.duration_ms,
            executed_at=response.executed_at,
            simulator_trace_id=response.meta.trace_id,
        )

    return mcp
