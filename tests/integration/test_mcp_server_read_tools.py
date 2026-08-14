"""alarm-management MCP server over a real transport, against the real seeded
(compact-profile) simulator -- no mocks anywhere in the chain (same pattern as
tests/integration/test_mcp_server_search_assets.py, extended to the 9 read tools added
in 02-phases.md Phase 4). One happy-path test per tool, plus 2 trace-propagation tests
proving MCP `_meta` reaches the simulator's echoed `meta.trace_id` and back.

Seeded values (asset ids, units, time windows, calculation types) are pinned to the
same fixtures already exercised against this dataset in
tests/integration/test_route_alarms.py, test_route_analytics.py, and
test_route_recommendations_and_kpi.py.
"""

from __future__ import annotations

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

START = "2026-05-01T00:00:00Z"
END = "2026-07-01T00:00:00Z"


async def test_list_alarms_returns_alarms_for_an_asset(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool("list_alarms", {"asset_id": "NP-U1-BFP-101"})

        assert result.isError is False
        body = result.structuredContent
        assert body["total"] >= 1
        assert body["alarms"][0]["alarm_id"].startswith("ALM-")
        assert isinstance(body["truncated"], bool)


async def test_get_alarm_summary_returns_grouped_kpis(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "get_alarm_summary",
            {
                "asset_ids": ["NP-U1-BFP-101"],
                "start_time": START,
                "end_time": END,
                "severity": ["high", "critical"],
                "group_by": ["alarm_name"],
                "kpis": ["alarm_count", "recurring_rate", "avg_ack_delay"],
            },
        )

        assert result.isError is False
        body = result.structuredContent
        assert set(body["groups"][0]["kpis"]) == {"alarm_count", "recurring_rate", "avg_ack_delay"}


async def test_get_alarm_trends_returns_daily_series(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "get_alarm_trends",
            {
                "asset_ids": ["NP-U1-BFP-101"],
                "start_time": START,
                "end_time": END,
                "bucket": "daily",
                "metrics": ["alarm_count", "avg_ack_delay"],
            },
        )

        assert result.isError is False
        body = result.structuredContent
        assert body["bucket"] == "daily"
        assert {s["metric"] for s in body["series"]} == {"alarm_count", "avg_ack_delay"}


async def test_analyze_alarm_flood_finds_a_flood_window(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "analyze_alarm_flood",
            {
                "unit": "Unit 2",
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": END,
                "threshold_count": 10,
                "rolling_window_minutes": 10,
            },
        )

        assert result.isError is False
        body = result.structuredContent
        assert len(body["flood_windows"]) >= 1
        assert body["flood_windows"][0]["alarm_count"] > 10


async def test_get_rationalization_candidates_finds_a_recurring_candidate(
    mcp_alarm_server_url: str,
) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "get_rationalization_candidates",
            {
                "asset_ids": ["NP-U1-BFP-101"],
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": END,
                "recurrence_threshold": 5,
                "stale_minutes_threshold": 180,
            },
        )

        assert result.isError is False
        body = result.structuredContent
        assert body["total"] >= 1
        assert all("category" in c and "reason" in c for c in body["candidates"])


async def test_correlate_alarms_returns_pairs_for_compressors(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        assets = await session.call_tool("search_assets", {"query": "compressor", "unit": "Unit 3"})
        asset_ids = [a["asset_id"] for a in assets.structuredContent["results"][:3]]

        result = await session.call_tool(
            "correlate_alarms",
            {
                "asset_ids": asset_ids,
                "start_time": START,
                "end_time": END,
                "correlation_method": "cooccurrence",
                "lag_window_minutes": 15,
                "severity_threshold": "medium",
                "min_support": 1,
            },
        )

        assert result.isError is False
        body = result.structuredContent
        assert "pairs" in body
        assert body["method"] == "cooccurrence"


async def test_get_operator_recommendations_returns_a_rationalization_record(
    mcp_alarm_server_url: str,
) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        listing = await session.call_tool("list_alarms", {"asset_id": "NP-U1-BFP-101"})
        alarm_id = listing.structuredContent["alarms"][0]["alarm_id"]

        result = await session.call_tool(
            "get_operator_recommendations",
            {"alarm_id": alarm_id, "include_related": True, "include_asset_context": True},
        )

        assert result.isError is False
        body = result.structuredContent
        assert body["alarm_id"] == alarm_id
        assert len(body["immediate_actions"]) >= 1
        assert body["rationalization_record"]["cause"]


async def test_generate_kpi_calculation_returns_visible_code(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "generate_kpi_calculation",
            {
                "calculation_type": "nuisance_alarm_score",
                "unit": "Unit 4",
                "start_time": START,
                "end_time": END,
            },
        )

        assert result.isError is False
        body = result.structuredContent
        assert body["calculation_id"]
        assert "def" in body["code"]


async def test_execute_kpi_calculation_runs_a_generated_calculation(
    mcp_alarm_server_url: str,
) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        filters = {"unit": "Unit 3", "start_time": START, "end_time": END}
        generated = await session.call_tool(
            "generate_kpi_calculation", {"calculation_type": "critical_alarm_density", **filters}
        )
        calculation_id = generated.structuredContent["calculation_id"]

        result = await session.call_tool(
            "execute_kpi_calculation", {"calculation_id": calculation_id, **filters}
        )

        assert result.isError is False
        body = result.structuredContent
        assert body["calculation_id"] == calculation_id
        assert body["status"] == "completed"
        assert body["result"]


async def test_trace_id_propagates_through_list_alarms(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "list_alarms",
            {"asset_id": "NP-U1-BFP-101"},
            meta={"trace_id": "trace-list-alarms-e2e"},
        )

        assert result.isError is False
        assert result.structuredContent["simulator_trace_id"] == "trace-list-alarms-e2e"


async def test_trace_id_propagates_through_get_alarm_summary(mcp_alarm_server_url: str) -> None:
    async with (
        streamable_http_client(mcp_alarm_server_url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "get_alarm_summary",
            {"asset_ids": ["NP-U1-BFP-101"], "start_time": START, "end_time": END},
            meta={"trace_id": "trace-alarm-summary-e2e"},
        )

        assert result.isError is False
        assert result.structuredContent["simulator_trace_id"] == "trace-alarm-summary-e2e"
