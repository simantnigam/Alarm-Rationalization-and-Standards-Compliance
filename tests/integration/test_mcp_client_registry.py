"""copilot.mcp.McpToolRegistry: discovery, client-side schema validation, invocation,
and ToolInvocation recording -- the hand-written MCP client (D-02), first slice for the
walking skeleton (02-phases.md Phase 2.5). Phase 5 adds multi-server, lazy discovery
with backoff, and the stdio transport test on top of this same registry.
"""

from __future__ import annotations

import pytest

from copilot.domain.trace import ToolInvocation
from copilot.mcp.errors import ToolInputInvalid, ToolNotFound
from copilot.mcp.registry import McpServerConfig, McpToolRegistry


@pytest.fixture()
async def registry(mcp_alarm_server_url: str) -> McpToolRegistry:
    reg = McpToolRegistry([McpServerConfig(name="alarm-management", url=mcp_alarm_server_url)])
    await reg.discover()
    return reg


async def test_discover_populates_the_registry(registry: McpToolRegistry) -> None:
    assert registry.list_tools() == ["search_assets"]


async def test_call_tool_returns_a_tool_invocation_with_real_data(
    registry: McpToolRegistry,
) -> None:
    invocation = await registry.call_tool(
        "search_assets", {"query": "Boiler Feed Pump 101"}, trace_id="trace-1"
    )
    assert isinstance(invocation, ToolInvocation)
    assert invocation.ok is True
    assert invocation.tool_name == "search_assets"
    assert invocation.server == "alarm-management"
    assert invocation.trace_id == "trace-1"
    assert invocation.duration_ms >= 0
    assert invocation.result["results"][0]["asset_id"] == "NP-U1-BFP-101"


async def test_trace_id_propagates_end_to_end_to_the_simulators_echoed_meta(
    registry: McpToolRegistry,
) -> None:
    """The exit-gate requirement, proven mechanically: MCP client _meta -> tool ctx ->
    connector HTTP header -> simulator TraceMiddleware -> simulator response meta ->
    connector-parsed meta -> tool output -> here. Not asserted in a document.
    """
    invocation = await registry.call_tool(
        "search_assets", {"query": "Boiler Feed Pump 101"}, trace_id="trace-propagation-e2e"
    )
    assert invocation.ok is True
    assert invocation.result["simulator_trace_id"] == "trace-propagation-e2e"


async def test_call_unknown_tool_raises_tool_not_found(registry: McpToolRegistry) -> None:
    with pytest.raises(ToolNotFound):
        await registry.call_tool("does_not_exist", {}, trace_id="trace-1")


async def test_invalid_arguments_are_caught_client_side_before_dispatch(
    registry: McpToolRegistry,
) -> None:
    # limit must be an integer per the tool's input schema -- this must never reach the
    # network; jsonschema validation catches it locally.
    with pytest.raises(ToolInputInvalid):
        await registry.call_tool(
            "search_assets", {"query": "pump", "limit": "not-a-number"}, trace_id="trace-1"
        )
