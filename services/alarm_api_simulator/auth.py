"""Bearer auth on every route except /health. 401 on missing/invalid -- never echoing
the presented token (§17; 01-architecture.md §3).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException, Request

from alarm_api_simulator.config import SimulatorSettings


@lru_cache
def get_settings() -> SimulatorSettings:
    """Used only by the standalone entrypoint (`python -m alarm_api_simulator`); route
    dependencies read `request.app.state.settings` instead, so a test app never
    depends on process environment variables.
    """
    return SimulatorSettings()  # type: ignore[call-arg]


async def require_bearer_token(
    request: Request, authorization: str | None = Header(default=None)
) -> None:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ")
    settings: SimulatorSettings = request.app.state.settings
    if token != settings.alarm_api_token:
        raise HTTPException(status_code=401, detail="invalid token")
