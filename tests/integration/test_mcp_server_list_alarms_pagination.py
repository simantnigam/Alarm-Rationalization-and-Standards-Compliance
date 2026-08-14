"""list_alarms auto-paginates GET /alarms internally and surfaces a `truncated` flag
instead of exposing raw page/page_size controls to the caller (01-architecture.md
§5.1's "auto-paginate, capped", 02-phases.md Phase 4). This is a tool-layer behavior,
distinct from connectors.alarm_api.client.paginate_alarms's own hard cap + log warning
(tests/unit/test_connector_list_alarms.py) -- the MCP tool owns its own bounded
aggregation loop so it can turn the cap into a queryable output field instead of a log
line only.
"""

from __future__ import annotations

import httpx
import respx
from mcp.shared.memory import create_connected_server_and_client_session

from connectors.alarm_api.client import AlarmApiClient
from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.server import build_server

BASE_URL = "http://fake-alarm-api.test"
TOKEN = "test-token"


def _alarm(alarm_id: str) -> dict:
    return {
        "alarm_id": alarm_id,
        "alarm_code": "BFP101-VIB-HH",
        "asset_id": "NP-U1-BFP-101",
        "asset_name": "Boiler Feed Pump 101",
        "site": "NorthPlant",
        "unit": "Unit 1",
        "alarm_name": "Vibration High-High",
        "alarm_type": "process",
        "severity": "high",
        "is_sif_related": False,
        "start_time": "2026-05-01T00:00:00Z",
        "status": "cleared",
    }


def _page(*, data: list[dict], page: int, total_pages: int, has_more: bool) -> dict:
    return {
        "data": data,
        "page": page,
        "page_size": 2,
        "total": total_pages * 2,
        "total_pages": total_pages,
        "has_more": has_more,
        "sort_by": "start_time",
        "sort_order": "desc",
        "meta": {"trace_id": "trace-pagination"},
    }


async def _call_list_alarms() -> dict:
    client = AlarmApiClient(base_url=BASE_URL, token=TOKEN)
    settings = AlarmMcpSettings(alarm_api_token=TOKEN, alarm_api_base_url=BASE_URL)
    mcp = build_server(settings, client=client)

    async with create_connected_server_and_client_session(mcp) as session:
        result = await session.call_tool("list_alarms", {"asset_id": "NP-U1-BFP-101"})

    assert result.isError is False
    assert result.structuredContent is not None
    return result.structuredContent


@respx.mock
async def test_multi_page_results_are_assembled_into_one_list() -> None:
    respx.get(f"{BASE_URL}/alarms").mock(
        side_effect=[
            httpx.Response(
                200,
                json=_page(data=[_alarm("A1"), _alarm("A2")], page=1, total_pages=3, has_more=True),
            ),
            httpx.Response(
                200,
                json=_page(data=[_alarm("A3"), _alarm("A4")], page=2, total_pages=3, has_more=True),
            ),
            httpx.Response(
                200, json=_page(data=[_alarm("A5")], page=3, total_pages=3, has_more=False)
            ),
        ]
    )
    structured = await _call_list_alarms()

    assert [a["alarm_id"] for a in structured["alarms"]] == ["A1", "A2", "A3", "A4", "A5"]
    assert structured["total"] == 5
    assert structured["truncated"] is False


@respx.mock
async def test_natural_exhaustion_on_a_single_page_is_not_truncated() -> None:
    respx.get(f"{BASE_URL}/alarms").mock(
        return_value=httpx.Response(
            200, json=_page(data=[_alarm("A1")], page=1, total_pages=1, has_more=False)
        )
    )
    structured = await _call_list_alarms()

    assert structured["total"] == 1
    assert structured["truncated"] is False


@respx.mock
async def test_hitting_the_hard_page_cap_sets_truncated_true() -> None:
    route = respx.get(f"{BASE_URL}/alarms").mock(
        return_value=httpx.Response(
            200, json=_page(data=[_alarm("A1")], page=1, total_pages=1000, has_more=True)
        )
    )
    structured = await _call_list_alarms()

    assert structured["truncated"] is True
    # The tool stopped at its own internal page cap, not because the upstream ran out.
    assert route.call_count == structured["total"]
    assert structured["total"] < 1000
