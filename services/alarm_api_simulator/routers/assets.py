"""GET /assets/search (pinned by Postman: body.results[0].asset_id) and
GET /assets/{id}/metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from alarm_api_simulator.auth import require_bearer_token
from alarm_api_simulator.db.schema import alarm_definitions, alarms, assets
from alarm_api_simulator.faults import apply_fault_injection, malformed_response
from alarm_api_simulator.trace import build_meta

router = APIRouter(dependencies=[Depends(require_bearer_token), Depends(apply_fault_injection)])


@router.get("/assets/search")
def search_assets(
    request: Request,
    query: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=200),
    unit: str | None = Query(default=None),
    site: str | None = Query(default=None),
) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    stmt = select(assets)
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(assets.c.asset_name.ilike(pattern), assets.c.asset_type.ilike(pattern))
        )
    if unit:
        stmt = stmt.where(assets.c.unit == unit)
    if site:
        stmt = stmt.where(assets.c.site == site)

    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = conn.execute(stmt.order_by(assets.c.asset_id).limit(limit)).mappings().all()

    return {
        "results": [dict(r) for r in rows],
        "total": total,
        "query": query,
        "limit": limit,
        "meta": build_meta(request, sim_profile=settings.sim_profile),
    }


@router.get("/assets/{asset_id}/metadata")
def asset_metadata(asset_id: str, request: Request) -> dict[str, object]:
    if getattr(request.state, "malformed_response", False):
        return malformed_response()  # type: ignore[return-value]

    engine = request.app.state.engine
    settings = request.app.state.settings

    with engine.connect() as conn:
        row = conn.execute(select(assets).where(assets.c.asset_id == asset_id)).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="asset not found")

        alarm_code_count = conn.execute(
            select(func.count())
            .select_from(alarm_definitions)
            .where(alarm_definitions.c.asset_id == asset_id)
        ).scalar_one()
        active_alarm_count = conn.execute(
            select(func.count())
            .select_from(alarms)
            .where(alarms.c.asset_id == asset_id, alarms.c.status == "active")
        ).scalar_one()

    body = dict(row)
    body["alarm_code_count"] = alarm_code_count
    body["active_alarm_count"] = active_alarm_count
    body["meta"] = build_meta(request, sim_profile=settings.sim_profile)
    return body
