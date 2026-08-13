"""Trace propagation: `trace_id` / `x-client-id` / `x-metadata-tag` are accepted,
logged, and echoed in a `meta` block on every response (01-architecture.md §3). This is
what makes propagation assertable end-to-end: GUI request-id -> copilot -> MCP `_meta`
-> HTTP header -> simulator -> response -> trace panel.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from alarm_api_simulator.timeutil import iso_z


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid.uuid4())
        request.state.trace_id = request.headers.get("trace_id") or request.state.request_id
        request.state.client_id = request.headers.get("x-client-id")
        request.state.metadata_tag = request.headers.get("x-metadata-tag")
        request.state.started_at = time.monotonic()
        return await call_next(request)


def build_meta(request: Request, *, sim_profile: str) -> dict[str, object]:
    started_at = getattr(request.state, "started_at", time.monotonic())
    return {
        "request_id": getattr(request.state, "request_id", None),
        "trace_id": getattr(request.state, "trace_id", None),
        "client_id": getattr(request.state, "client_id", None),
        "metadata_tag": getattr(request.state, "metadata_tag", None),
        "generated_at": iso_z(datetime.now(UTC)),
        "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
        "sim_profile": sim_profile,
    }
