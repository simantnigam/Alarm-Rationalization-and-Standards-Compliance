"""alarm-management MCP server discovery and input validation, over the in-memory MCP
transport (no live simulator needed -- discovery and malformed-input rejection never
reach the connector). 02-phases.md Phase 4 exit gate: "registration and discovery lists
exactly 10 tools with schemas; each tool rejects malformed input with a field-level
error." (The plan text's own "12" is a leftover from before the write-path tools were
rescoped to Phase 9 -- confirmed with the user; 10 is authoritative for this phase.)

FastMCP registers its lowlevel call_tool handler with `validate_input=False` (it does
its own ad hoc argument conversion before validating) and instead validates arguments
against the tool's auto-generated Pydantic model inside `Tool.run`. A validation
failure there is caught by `Tool.run`'s generic `except Exception` and re-raised as
`ToolError(f"Error executing tool {name}: {e}")`, so the field-level detail is *inside*
the message, not the whole message -- assert containment, not a prefix.
"""

from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.server import build_server

EXPECTED_TOOLS = {
    "search_assets",
    "list_alarms",
    "get_alarm_summary",
    "get_alarm_trends",
    "analyze_alarm_flood",
    "get_rationalization_candidates",
    "correlate_alarms",
    "get_operator_recommendations",
    "generate_kpi_calculation",
    "execute_kpi_calculation",
}


def _text(result: object) -> str:
    content = getattr(result, "content")  # noqa: B009
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return str(text)
    return ""


async def test_discovery_lists_exactly_10_tools_with_input_and_output_schemas() -> None:
    settings = AlarmMcpSettings(alarm_api_token="test-token")
    mcp = build_server(settings)

    async with create_connected_server_and_client_session(mcp) as session:
        listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        assert names == EXPECTED_TOOLS

        for tool in listed.tools:
            assert tool.inputSchema is not None
            assert tool.outputSchema is not None


async def test_list_alarms_rejects_malformed_input_with_a_field_level_error() -> None:
    settings = AlarmMcpSettings(alarm_api_token="test-token")
    mcp = build_server(settings)

    async with create_connected_server_and_client_session(mcp) as session:
        # `unit` must be a string per the tool's schema -- an int must never reach the
        # connector.
        result = await session.call_tool("list_alarms", {"unit": 42})

    assert result.isError is True
    text = _text(result)
    assert "unit" in text


async def test_get_alarm_summary_rejects_malformed_input_with_a_field_level_error() -> None:
    settings = AlarmMcpSettings(alarm_api_token="test-token")
    mcp = build_server(settings)

    async with create_connected_server_and_client_session(mcp) as session:
        # `severity` must be a list[str] per the tool's schema -- a bare string must
        # never reach the connector.
        result = await session.call_tool("get_alarm_summary", {"severity": "high"})

    assert result.isError is True
    text = _text(result)
    assert "severity" in text
