"""Settings for the alarm-management MCP server. Holds the Alarm API token itself --
the copilot's MCP client never sees it (D-05)."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AlarmMcpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    alarm_api_base_url: str = "http://alarm-api:8000"
    alarm_api_token: str  # required -- secret, no default

    mcp_transport: Literal["stdio", "http"] = "http"
    mcp_alarm_host: str = "0.0.0.0"
    mcp_alarm_port: int = 9000

    # DNS-rebinding Host-header allowlist (comma-separated). Defaults cover local dev
    # and tests (dynamic ports); docker-compose.yml adds the service DNS name.
    mcp_allowed_hosts: str = "127.0.0.1:*,localhost:*"

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.mcp_allowed_hosts.split(",") if h.strip()]
