"""FastAPI app factory. `engine` and `settings` are constructor arguments (not process
globals) so tests can bind a seeded test database without touching environment
variables -- the same app code runs in tests, in `python -m alarm_api_simulator`, and
in the Docker image.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import Engine

from alarm_api_simulator.config import SimulatorSettings
from alarm_api_simulator.routers import (
    alarms,
    analytics,
    assets,
    calculations,
    health,
    kpi_definitions,
    recommendations,
)
from alarm_api_simulator.trace import TraceMiddleware


def create_app(*, engine: Engine, settings: SimulatorSettings) -> FastAPI:
    app = FastAPI(title="Alarm Management API Simulator", version="0.1.0")
    app.state.engine = engine
    app.state.settings = settings

    app.add_middleware(TraceMiddleware)

    app.include_router(health.router)
    app.include_router(assets.router)
    app.include_router(alarms.router)
    app.include_router(analytics.router)
    app.include_router(recommendations.router)
    app.include_router(calculations.router)
    app.include_router(kpi_definitions.router)

    return app
