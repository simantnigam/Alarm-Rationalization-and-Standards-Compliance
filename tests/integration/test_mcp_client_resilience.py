"""McpToolRegistry's Phase 5 additions on top of the Phase 2.5 walking-skeleton slice
(tests/integration/test_mcp_client_registry.py): multi-server discovery that tolerates a
down server (R-04), background backoff retry, a per-call timeout + retry policy distinct
from the connector's, and transport coverage across memory / stdio / http
(02-phases.md Phase 5's test bullet).

A tiny in-memory FastMCP "toy" server (no mcp_servers.alarm_management import -- the
copilot must only ever know a real MCP server by config, never by importing its
implementation) stands in for a second server so multi-server and timeout/retry
scenarios don't need Postgres or the live simulator.
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp.server.fastmcp import FastMCP

from copilot.mcp.registry import McpServerConfig, McpToolRegistry

UNREACHABLE_URL = "http://127.0.0.1:1"


def _toy_server() -> FastMCP:
    mcp = FastMCP(name="toy")

    @mcp.tool(name="echo")
    async def echo(message: str) -> dict[str, str]:
        return {"message": message}

    return mcp


# --- transport coverage ------------------------------------------------------------


async def test_discovery_and_invocation_over_in_memory_transport() -> None:
    registry = McpToolRegistry(
        [McpServerConfig(name="toy", transport="memory", server=_toy_server())]
    )
    await registry.discover()

    assert registry.degraded is False
    assert registry.list_tools() == ["echo"]

    invocation = await registry.call_tool("echo", {"message": "hi"}, trace_id="t1")
    assert invocation.ok is True
    assert invocation.result["message"] == "hi"


async def test_discovery_and_invocation_over_stdio_transport(
    live_simulator_url: str, alarm_api_test_token: str
) -> None:
    server = McpServerConfig(
        name="alarm-management-stdio",
        transport="stdio",
        command=sys.executable,
        args=("-m", "mcp_servers.alarm_management"),
        env={
            **os.environ,
            "ALARM_API_BASE_URL": live_simulator_url,
            "ALARM_API_TOKEN": alarm_api_test_token,
            "MCP_TRANSPORT": "stdio",
        },
    )
    registry = McpToolRegistry([server])
    await registry.discover()

    assert registry.degraded is False
    assert "search_assets" in registry.list_tools()

    invocation = await registry.call_tool(
        "search_assets", {"query": "Boiler Feed Pump 101"}, trace_id="trace-stdio"
    )
    assert invocation.ok is True
    assert invocation.result["results"][0]["asset_id"] == "NP-U1-BFP-101"


# --- multi-server discovery + partial failure (R-04) --------------------------------


async def test_discover_populates_tools_from_multiple_servers(mcp_alarm_server_url: str) -> None:
    registry = McpToolRegistry(
        [
            McpServerConfig(name="toy", transport="memory", server=_toy_server()),
            McpServerConfig(name="alarm-management", url=mcp_alarm_server_url),
        ]
    )
    await registry.discover()

    assert registry.degraded is False
    assert "echo" in registry.list_tools()
    assert "search_assets" in registry.list_tools()


async def test_a_down_server_does_not_block_discovery_of_the_other_or_its_calls() -> None:
    registry = McpToolRegistry(
        [
            McpServerConfig(name="toy", transport="memory", server=_toy_server()),
            McpServerConfig(name="down", url=UNREACHABLE_URL),
        ]
    )
    await registry.discover()

    assert registry.degraded is True
    assert registry.degraded_servers() == ["down"]
    assert "echo" in registry.list_tools()

    invocation = await registry.call_tool("echo", {"message": "hi"}, trace_id="t1")
    assert invocation.ok is True


# --- discover_with_backoff (R-04) ----------------------------------------------------


async def test_discover_with_backoff_retries_a_degraded_server_until_it_recovers() -> None:
    registry = McpToolRegistry(
        [McpServerConfig(name="flaky", url=UNREACHABLE_URL)],
        discovery_backoff_base=0.001,
        discovery_backoff_cap=0.01,
    )
    await registry.discover()
    assert registry.degraded is True

    attempts = 0

    async def fake_discover_one(server: McpServerConfig) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return False
        registry._discovered.add(server.name)
        return True

    registry._discover_one = fake_discover_one  # type: ignore[method-assign]

    await registry.discover_with_backoff()

    assert attempts == 3
    assert registry.degraded is False


async def test_discover_with_backoff_stops_after_max_attempts_if_still_degraded() -> None:
    registry = McpToolRegistry(
        [McpServerConfig(name="always-down", url=UNREACHABLE_URL)],
        discovery_backoff_base=0.001,
        discovery_backoff_cap=0.01,
    )
    await registry.discover()
    assert registry.degraded is True

    attempts = 0

    async def fake_discover_one(server: McpServerConfig) -> bool:
        nonlocal attempts
        attempts += 1
        return False

    registry._discover_one = fake_discover_one  # type: ignore[method-assign]

    await registry.discover_with_backoff(max_attempts=3)

    assert attempts == 3
    assert registry.degraded is True


# --- per-call timeout + retry policy (distinct from the connector's) ----------------


async def test_call_tool_times_out_and_records_a_failed_invocation() -> None:
    mcp = FastMCP(name="toy")

    @mcp.tool(name="slow")
    async def slow() -> dict:
        await asyncio.sleep(5)
        return {}

    registry = McpToolRegistry(
        [McpServerConfig(name="toy", transport="memory", server=mcp)],
        call_timeout=0.05,
        max_call_attempts=1,
    )
    await registry.discover()

    invocation = await registry.call_tool("slow", {}, trace_id="t1")

    assert invocation.ok is False
    assert invocation.error_code == "TIMEOUT"


async def test_call_tool_retries_after_a_timeout_and_then_succeeds() -> None:
    mcp = FastMCP(name="toy")
    call_count = 0

    @mcp.tool(name="flaky_once")
    async def flaky_once() -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(5)
        return {"attempt": call_count}

    registry = McpToolRegistry(
        [McpServerConfig(name="toy", transport="memory", server=mcp)],
        call_timeout=0.05,
        max_call_attempts=2,
        call_retry_delay=0.001,
    )
    await registry.discover()

    invocation = await registry.call_tool("flaky_once", {}, trace_id="t1")

    assert invocation.ok is True
    assert invocation.retry_count == 1
    assert call_count == 2


async def test_tool_level_errors_are_returned_immediately_without_retrying() -> None:
    mcp = FastMCP(name="toy")
    call_count = 0

    @mcp.tool(name="boom")
    async def boom() -> dict:
        nonlocal call_count
        call_count += 1
        raise ValueError("nope")

    registry = McpToolRegistry(
        [McpServerConfig(name="toy", transport="memory", server=mcp)], max_call_attempts=3
    )
    await registry.discover()

    invocation = await registry.call_tool("boom", {}, trace_id="t1")

    assert invocation.ok is False
    assert invocation.error_code == "TOOL_ERROR"
    assert call_count == 1
