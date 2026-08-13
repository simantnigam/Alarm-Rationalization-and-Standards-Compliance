"""Copilot backend app factory. `graph` is a constructor argument, not a process
global, so tests bind a graph wired to test doubles/live-test fixtures without touching
environment variables -- the same pattern used by alarm_api_simulator.main.create_app.
"""

from __future__ import annotations

from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph

from copilot.api.routes import router


def create_app(*, graph: CompiledStateGraph) -> FastAPI:
    app = FastAPI(title="Alarm Rationalization Copilot")
    app.state.graph = graph
    app.include_router(router)
    return app
