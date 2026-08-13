"""POST /calculation-code/generate and POST /calculation-code/execute -- the
controlled KPI flow (4.5.3x). `execute` accepts only a `calculation_id` previously
issued by `generate`; it never accepts or evaluates model-authored code.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import insert, select, update

from alarm_api_simulator.analytics.calculations import (
    DESCRIPTIONS,
    generate_code,
    input_schema_for,
    output_schema_for,
    run_calculation,
)
from alarm_api_simulator.analytics.queries import fetch_filtered_alarms
from alarm_api_simulator.auth import require_bearer_token
from alarm_api_simulator.db.schema import calculation_runs
from alarm_api_simulator.faults import apply_fault_injection, malformed_response
from alarm_api_simulator.schemas import ExecuteCalculationRequest, GenerateCalculationRequest
from alarm_api_simulator.timeutil import iso_z
from alarm_api_simulator.trace import build_meta

router = APIRouter(dependencies=[Depends(require_bearer_token), Depends(apply_fault_injection)])


@router.post("/calculation-code/generate")
def generate_calculation(body: GenerateCalculationRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    calculation_id = f"calc-{uuid.uuid4().hex[:12]}"
    filters = body.filters.model_dump(mode="json")
    code = generate_code(body.calculation_type, filters)
    created_at = datetime.now(UTC)

    with engine.begin() as conn:
        conn.execute(
            insert(calculation_runs).values(
                calculation_id=calculation_id,
                calculation_type=body.calculation_type,
                filters_json=filters,
                generated_code=code,
                status="generated",
                result_json=None,
                created_at=created_at,
                executed_at=None,
                duration_ms=None,
            )
        )

    return {
        "calculation_id": calculation_id,
        "calculation_type": body.calculation_type,
        "code": code,
        "language": "python",
        "description": DESCRIPTIONS[body.calculation_type],
        "input_schema": input_schema_for(body.calculation_type),
        "output_schema": output_schema_for(body.calculation_type),
        "created_at": iso_z(created_at),
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }


@router.post("/calculation-code/execute")
def execute_calculation(body: ExecuteCalculationRequest, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    with engine.connect() as conn:
        run_row = (
            conn.execute(
                select(calculation_runs).where(
                    calculation_runs.c.calculation_id == body.calculation_id
                )
            )
            .mappings()
            .first()
        )
    if run_row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "unknown calculation_id -- only ids issued by "
                "/calculation-code/generate are accepted"
            ),
        )

    started = time.monotonic()
    rows = fetch_filtered_alarms(
        engine,
        unit=body.filters.unit,
        site=body.filters.site,
        start_time=body.filters.start_time,
        end_time=body.filters.end_time,
    )
    result = run_calculation(run_row["calculation_type"], rows)
    duration_ms = round((time.monotonic() - started) * 1000, 2)
    executed_at = datetime.now(UTC)

    with engine.begin() as conn:
        conn.execute(
            update(calculation_runs)
            .where(calculation_runs.c.calculation_id == body.calculation_id)
            .values(
                status="completed",
                result_json=result,
                executed_at=executed_at,
                duration_ms=duration_ms,
            )
        )

    return {
        "calculation_id": body.calculation_id,
        "calculation_type": run_row["calculation_type"],
        "status": "completed",
        "result": result,
        "row_count": len(rows),
        "duration_ms": duration_ms,
        "executed_at": iso_z(executed_at),
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }
