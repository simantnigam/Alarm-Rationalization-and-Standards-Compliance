"""Fault injection (D-09): `X-Simulate-Fault: timeout|500|429|malformed`, or `?fault=`
for browser/demo use. Makes retry/timeout/error-mapping tests exercise real failures,
and gives the required degraded-scenario demo a reproducible trigger.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

TIMEOUT_FAULT_DELAY_S = 30.0


def _requested_fault(request: Request) -> str | None:
    header = request.headers.get("x-simulate-fault")
    query = request.query_params.get("fault")
    return header or query


async def apply_fault_injection(request: Request) -> None:
    """A dependency: raises/sleeps before the route body runs when a fault is requested."""
    fault = _requested_fault(request)
    if fault is None:
        return
    if fault == "timeout":
        await asyncio.sleep(TIMEOUT_FAULT_DELAY_S)
    elif fault == "500":
        raise HTTPException(status_code=500, detail="simulated upstream failure")
    elif fault == "429":
        raise HTTPException(
            status_code=429, detail="simulated rate limit", headers={"Retry-After": "1"}
        )
    elif fault == "malformed":
        # Signals the route to return a body that violates its own response contract.
        request.state.malformed_response = True
    else:
        raise HTTPException(status_code=400, detail=f"unknown fault: {fault!r}")


def malformed_response() -> JSONResponse:
    return JSONResponse(status_code=200, content={"unexpected": "shape", "missing": "everything"})
