"""GET /alarms (pinned: body.data[0].alarm_id) and GET /alarms/{id}. `sort_by` and
`sort_order` are validated against an allowlist before use -- ORDER BY cannot be
parameterized, so this is where an injection attempt through those fields would land.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import asc, desc, func, select

from alarm_api_simulator.auth import require_bearer_token
from alarm_api_simulator.db.schema import alarm_definitions, alarms
from alarm_api_simulator.faults import apply_fault_injection, malformed_response
from alarm_api_simulator.trace import build_meta

router = APIRouter(dependencies=[Depends(require_bearer_token), Depends(apply_fault_injection)])

_SORT_COLUMNS = {
    "start_time": alarms.c.start_time,
    "end_time": alarms.c.end_time,
    "severity": alarms.c.severity,
    "status": alarms.c.status,
    "alarm_code": alarms.c.alarm_code,
    "asset_id": alarms.c.asset_id,
    "duration_s": alarms.c.duration_s,
}
SortBy = Literal[
    "start_time", "end_time", "severity", "status", "alarm_code", "asset_id", "duration_s"
]
SortOrder = Literal["asc", "desc"]
AlarmStatus = Literal["active", "acknowledged", "cleared", "shelved", "suppressed"]


@router.get("/alarms")
def list_alarms(
    request: Request,
    asset_id: str | None = Query(default=None),
    unit: str | None = Query(default=None),
    site: str | None = Query(default=None),
    status: AlarmStatus | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: SortBy = Query(default="start_time"),
    sort_order: SortOrder = Query(default="desc"),
) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    stmt = select(alarms)
    if asset_id:
        stmt = stmt.where(alarms.c.asset_id == asset_id)
    if unit:
        stmt = stmt.where(alarms.c.unit == unit)
    if site:
        stmt = stmt.where(alarms.c.site == site)
    if status:
        stmt = stmt.where(alarms.c.status == status)
    if start_time:
        stmt = stmt.where(alarms.c.start_time >= start_time)
    if end_time:
        stmt = stmt.where(alarms.c.start_time <= end_time)

    order_fn = asc if sort_order == "asc" else desc
    stmt = stmt.order_by(order_fn(_SORT_COLUMNS[sort_by]))

    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = conn.execute(stmt.limit(page_size).offset((page - 1) * page_size)).mappings().all()

    total_pages = max(1, -(-total // page_size))
    return {
        "data": [dict(r) for r in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_more": page < total_pages,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }


@router.get("/alarms/{alarm_id}")
def get_alarm(alarm_id: str, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    with engine.connect() as conn:
        row = conn.execute(select(alarms).where(alarms.c.alarm_id == alarm_id)).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="alarm not found")
        definition = (
            conn.execute(
                select(alarm_definitions).where(alarm_definitions.c.alarm_code == row["alarm_code"])
            )
            .mappings()
            .first()
        )

    body = dict(row)
    body["definition"] = {
        "cause": definition["cause"],
        "consequence": definition["consequence"],
        "corrective_action": definition["corrective_action"],
        "allowable_response_time_s": definition["allowable_response_time_s"],
        "setpoint": definition["setpoint"],
        "deadband": definition["deadband"],
    }
    body["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return body
