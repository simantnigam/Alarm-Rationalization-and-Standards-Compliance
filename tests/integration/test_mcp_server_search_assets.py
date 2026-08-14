"""alarm-management MCP server over a real transport (D-08's "real transport, real
auth header" requirement for the walking skeleton, 02-phases.md Phase 2.5). The tool
calls the real connector, which calls the real (seeded) simulator -- no mocks anywhere
in this chain.
"""

from __future__ import annotations

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def test_search_assets_tool_is_discoverable(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        # The full 10-tool roster is asserted in test_mcp_server_discovery.py -- this
        # file only cares that search_assets itself is discoverable and well-formed.
        assert "search_assets" in names
        tool = next(t for t in listed.tools if t.name == "search_assets")
        assert "query" in tool.inputSchema["properties"]
        assert tool.outputSchema is not None


async def test_call_search_assets_returns_real_data_from_the_simulator(
    mcp_alarm_server_url: str,
) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "search_assets", {"query": "Boiler Feed Pump 101", "limit": 10}
        )
        assert result.isError is False
        assert result.structuredContent is not None
        assert result.structuredContent["results"][0]["asset_id"] == "NP-U1-BFP-101"


async def test_call_search_assets_with_no_matches_returns_empty_not_error(
    mcp_alarm_server_url: str,
) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool("search_assets", {"query": "nonexistent-zzz"})
        assert result.isError is False
        assert result.structuredContent["results"] == []
