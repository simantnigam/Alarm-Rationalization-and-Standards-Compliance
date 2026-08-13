"""Independently runnable: `python -m mcp_servers.alarm_management` (§1.j, §2.1)."""

from __future__ import annotations

from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.server import build_server


def main() -> None:  # pragma: no cover -- process entrypoint
    settings = AlarmMcpSettings()  # type: ignore[call-arg]
    mcp = build_server(settings)
    mcp.settings.host = settings.mcp_alarm_host
    mcp.settings.port = settings.mcp_alarm_port

    if settings.mcp_transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":  # pragma: no cover
    main()
