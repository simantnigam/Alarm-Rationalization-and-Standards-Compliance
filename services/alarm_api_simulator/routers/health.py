"""GET /health -- no auth (§3: only route exempt from Bearer auth; Docker healthcheck
must stay open)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter()
_STARTED_AT = time.monotonic()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    engine = request.app.state.engine
    settings = request.app.state.settings

    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": request.app.version,
        "uptime_s": round(time.monotonic() - _STARTED_AT, 2),
        "dependencies": {"database": db_status},
        "sim_now": settings.sim_now,
        "sim_profile": settings.sim_profile,
        "seed": settings.sim_seed,
    }
