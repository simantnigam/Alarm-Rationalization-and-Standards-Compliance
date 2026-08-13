"""POST /recommendations/operator-actions. Actions and diagnostic steps are derived
from the alarm_definitions rationalization record (cause/consequence/corrective_action)
-- never invented -- so this returns documented actions, not model-authored ones.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from alarm_api_simulator.auth import require_bearer_token
from alarm_api_simulator.db.schema import alarm_definitions, alarms, assets
from alarm_api_simulator.faults import apply_fault_injection, malformed_response
from alarm_api_simulator.schemas import OperatorActionsRequest
from alarm_api_simulator.trace import build_meta

router = APIRouter(dependencies=[Depends(require_bearer_token), Depends(apply_fault_injection)])


@router.post("/recommendations/operator-actions")
def operator_recommendations(body: OperatorActionsRequest, request: Request) -> dict[str, object]:
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

        definition_row = (
            conn.execute(
                select(alarm_definitions).where(
                    alarm_definitions.c.alarm_code == alarm_row["alarm_code"]
                )
            )
            .mappings()
            .first()
        )

        asset_context = None
        if body.include_asset_context:
            asset_row = (
                conn.execute(select(assets).where(assets.c.asset_id == alarm_row["asset_id"]))
                .mappings()
                .first()
            )
            asset_context = dict(asset_row) if asset_row else None

        related_alarms = None
        if body.include_related:
            related_rows = (
                conn.execute(
                    select(alarms)
                    .where(
                        alarms.c.asset_id == alarm_row["asset_id"],
                        alarms.c.alarm_id != alarm_row["alarm_id"],
                    )
                    .order_by(alarms.c.start_time.desc())
                    .limit(5)
                )
                .mappings()
                .all()
            )
            related_alarms = [dict(r) for r in related_rows]

        historical_pattern = None
        if body.include_historical_pattern:
            code_rows = (
                conn.execute(select(alarms).where(alarms.c.alarm_code == alarm_row["alarm_code"]))
                .mappings()
                .all()
            )
            durations = [r["duration_s"] for r in code_rows if r["duration_s"] is not None]
            historical_pattern = {
                "occurrence_count": len(code_rows),
                "avg_duration_s": round(sum(durations) / len(durations), 2) if durations else 0.0,
            }

    immediate_actions = [
        f"Verify the {definition_row['measurement']} reading at {alarm_row['asset_name']} "
        f"against setpoint {definition_row['setpoint']}.",
        f"Acknowledge and log the {alarm_row['alarm_name']} alarm per site procedure.",
    ]
    diagnostic_steps = [
        f"Inspect {alarm_row['asset_name']} locally for signs consistent with: "
        f"{definition_row['cause']}",
        "Cross-check related alarms on the same asset for a common root cause.",
    ]

    return {
        "alarm_id": alarm_row["alarm_id"],
        "alarm_code": alarm_row["alarm_code"],
        "immediate_actions": immediate_actions,
        "diagnostic_steps": diagnostic_steps,
        "rationalization_record": {
            "cause": definition_row["cause"],
            "consequence": definition_row["consequence"],
            "corrective_action": definition_row["corrective_action"],
            "allowable_response_time_s": definition_row["allowable_response_time_s"],
        },
        "asset_context": asset_context,
        "related_alarms": related_alarms,
        "historical_pattern": historical_pattern,
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }
