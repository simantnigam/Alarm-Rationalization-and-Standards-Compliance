"""POST /alarms/{summary,trends,correlation,flood-analysis,rationalization-candidates}
and POST /alarms/priority-score. Aggregation logic lives in analytics/aggregation.py;
this module is wiring: parse request -> fetch filtered rows -> aggregate -> envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from alarm_api_simulator.analytics.aggregation import (
    compute_candidates,
    compute_correlation,
    compute_flood_windows,
    compute_trends,
    summarize,
)
from alarm_api_simulator.analytics.metrics import priority_score_factors
from alarm_api_simulator.analytics.queries import fetch_filtered_alarms
from alarm_api_simulator.auth import require_bearer_token
from alarm_api_simulator.db.schema import alarm_definitions, alarms, assets
from alarm_api_simulator.faults import apply_fault_injection, malformed_response
from alarm_api_simulator.schemas import (
    CandidatesRequest,
    CorrelationRequest,
    FloodRequest,
    PriorityScoreRequest,
    SummaryRequest,
    TrendsRequest,
)
from alarm_api_simulator.timeutil import iso_z
from alarm_api_simulator.trace import build_meta

router = APIRouter(dependencies=[Depends(require_bearer_token), Depends(apply_fault_injection)])


def _time_range_dict(body: object) -> dict[str, str] | None:
    time_range = getattr(body, "time_range", None)
    if time_range is None:
        return None
    return {
        "start_time": iso_z(time_range.start_time),
        "end_time": iso_z(time_range.end_time),
    }


@router.post("/alarms/summary")
def alarms_summary(body: SummaryRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    rows = fetch_filtered_alarms(
        engine,
        asset_ids=body.asset_ids,
        unit=body.unit,
        site=body.site,
        severity=body.severity,
        alarm_types=body.alarm_types,
        start_time=body.time_range.start_time if body.time_range else None,
        end_time=body.time_range.end_time if body.time_range else None,
    )
    try:
        result = summarize(rows, group_by=list(body.group_by))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if body.kpis:
        wanted = set(body.kpis)
        for group in result["groups"]:
            group["kpis"] = {k: v for k, v in group["kpis"].items() if k in wanted}
        result["totals"] = {k: v for k, v in result["totals"].items() if k in wanted}

    result["time_range"] = _time_range_dict(body)
    result["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return result


@router.post("/alarms/trends")
def alarms_trends(body: TrendsRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    rows = fetch_filtered_alarms(
        engine,
        asset_ids=body.asset_ids,
        unit=body.unit,
        site=body.site,
        start_time=body.time_range.start_time if body.time_range else None,
        end_time=body.time_range.end_time if body.time_range else None,
    )
    result = compute_trends(rows, bucket=body.bucket, metrics=body.metrics)
    result["time_range"] = _time_range_dict(body)
    result["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return result


@router.post("/alarms/correlation")
def alarms_correlation(body: CorrelationRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    rows = fetch_filtered_alarms(
        engine,
        asset_ids=body.asset_ids,
        unit=body.unit,
        site=body.site,
        start_time=body.time_range.start_time if body.time_range else None,
        end_time=body.time_range.end_time if body.time_range else None,
    )
    result = compute_correlation(
        rows,
        method=body.correlation_method,
        lag_window_minutes=body.lag_window_minutes,
        severity_threshold=body.severity_threshold,
        min_support=body.min_support,
    )
    result["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return result


@router.post("/alarms/flood-analysis")
def alarms_flood_analysis(body: FloodRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    rows = fetch_filtered_alarms(
        engine,
        unit=body.unit,
        site=body.site,
        start_time=body.time_range.start_time if body.time_range else None,
        end_time=body.time_range.end_time if body.time_range else None,
    )
    result = compute_flood_windows(
        rows,
        threshold_count=body.threshold_count,
        rolling_window_minutes=body.rolling_window_minutes,
    )
    result["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return result


@router.post("/alarms/rationalization-candidates")
def rationalization_candidates(body: CandidatesRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    rows = fetch_filtered_alarms(
        engine,
        asset_ids=body.asset_ids,
        unit=body.unit,
        site=body.site,
        start_time=body.time_range.start_time if body.time_range else None,
        end_time=body.time_range.end_time if body.time_range else None,
    )
    result = compute_candidates(
        rows,
        recurrence_threshold=body.recurrence_threshold,
        stale_minutes_threshold=body.stale_minutes_threshold,
        now=datetime.now(UTC),
    )
    result["thresholds"] = {
        "recurrence_threshold": body.recurrence_threshold,
        "stale_minutes_threshold": body.stale_minutes_threshold,
    }
    result["time_range"] = _time_range_dict(body)
    result["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return result


@router.post("/alarms/priority-score")
def priority_score_endpoint(body: PriorityScoreRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    with engine.connect() as conn:
        alarm_row = (
            conn.execute(select(alarms).where(alarms.c.alarm_id == body.alarm_id))
            .mappings()
            .first()
        )
        if alarm_row is None:
            raise HTTPException(status_code=404, detail="alarm not found")
        asset_row = (
            conn.execute(select(assets).where(assets.c.asset_id == alarm_row["asset_id"]))
            .mappings()
            .first()
        )
        definition_row = (
            conn.execute(
                select(alarm_definitions).where(
                    alarm_definitions.c.alarm_code == alarm_row["alarm_code"]
                )
            )
            .mappings()
            .first()
        )

    result = priority_score_factors(
        severity=alarm_row["severity"],
        criticality=asset_row["criticality"],
        allowable_response_time_s=definition_row["allowable_response_time_s"],
        is_sif_related=alarm_row["is_sif_related"],
    )
    score = result["score"]
    band = (
        "critical" if score >= 90 else "high" if score >= 70 else "medium" if score >= 40 else "low"
    )

    return {
        "alarm_id": alarm_row["alarm_id"],
        "alarm_code": alarm_row["alarm_code"],
        "priority_score": score,
        "priority_band": band,
        "current_severity": alarm_row["severity"],
        "recommended_priority": band,
        "factors": result["factors"],
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }
