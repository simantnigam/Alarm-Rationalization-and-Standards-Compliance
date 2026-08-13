"""GET /analytics/kpi-definitions: publishes every formula this simulator computes,
so the copilot can cite the formula rather than assert the number.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from alarm_api_simulator.auth import require_bearer_token
from alarm_api_simulator.db.schema import kpi_definitions
from alarm_api_simulator.faults import apply_fault_injection, malformed_response
from alarm_api_simulator.trace import build_meta

router = APIRouter(dependencies=[Depends(require_bearer_token), Depends(apply_fault_injection)])


@router.get("/analytics/kpi-definitions")
def list_kpi_definitions(request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    with engine.connect() as conn:
        rows = conn.execute(select(kpi_definitions)).mappings().all()

    return {
        "kpi_definitions": [dict(r) for r in rows],
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }
