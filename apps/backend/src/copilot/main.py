"""Copilot backend app factory. `graph` and `registry` are constructor arguments, not
process globals, so tests bind an app wired to test doubles/live-test fixtures without
touching environment variables -- the same pattern used by
alarm_api_simulator.main.create_app.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph

from copilot.api.routes import router
from copilot.mcp.registry import McpToolRegistry


def create_app(*, graph: CompiledStateGraph, registry: McpToolRegistry) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # The initial `discover()` pass already ran before create_app() was called;
        # this background task only keeps retrying whatever server(s) it missed
        # (R-04) so the process recovers without a restart once they come up.
        retry_task = asyncio.create_task(registry.discover_with_backoff())
        try:
            yield
        finally:
            retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await retry_task

    app = FastAPI(title="Alarm Rationalization Copilot", lifespan=lifespan)
    app.state.graph = graph
    app.state.registry = registry
    app.include_router(router)
    return app
