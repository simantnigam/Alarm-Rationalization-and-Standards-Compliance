"""Simulator settings. Scoped to what services/alarm_api_simulator itself needs --
the copilot backend has its own Settings (copilot.config) and does not share this one.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    alarm_api_host: str = "0.0.0.0"
    alarm_api_port: int = 8000
    alarm_api_token: str  # required -- Bearer token every non-/health route checks

    sim_profile: Literal["realistic", "compact", "golden"] = "realistic"
    sim_seed: int = 20260812
    sim_now: str | None = None  # ISO date; None => real now()

    alarmdb_host: str = "postgres"
    alarmdb_port: int = 5432
    alarmdb_name: str = "alarmdb"
    alarmdb_user: str = "alarmapi_rw"
    alarmdb_password: str  # required -- secret, no default

    log_level: str = "INFO"

    reseed_on_start: bool = Field(default=True)
