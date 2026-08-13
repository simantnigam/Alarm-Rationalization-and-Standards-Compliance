"""AlarmApiClient.list_alarms and paginate_alarms: pagination assembles across pages,
has_more is surfaced, and a hard page cap is enforced without silently truncating
(01-architecture.md §4; 02-phases.md Phase 3).
"""

from __future__ import annotations

import httpx
import pytest
import respx
import structlog.testing

from connectors.alarm_api.client import AlarmApiClient

BASE_URL = "http://alarm-api:8000"


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
        "meta": {},
    }


@pytest.fixture
def client() -> AlarmApiClient:
    return AlarmApiClient(base_url=BASE_URL, token="demo-token")


@respx.mock
async def test_list_alarms_single_page(client: AlarmApiClient) -> None:
    respx.get(f"{BASE_URL}/alarms").mock(
        return_value=httpx.Response(
            200,
            json=_page(data=[_alarm("A1"), _alarm("A2")], page=1, total_pages=1, has_more=False),
        )
    )
    result = await client.list_alarms(asset_id="NP-U1-BFP-101")

    assert len(result.data) == 2
    assert result.has_more is False


@respx.mock
async def test_paginate_alarms_assembles_across_pages(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/alarms")
    route.side_effect = [
        httpx.Response(
            200, json=_page(data=[_alarm("A1"), _alarm("A2")], page=1, total_pages=3, has_more=True)
        ),
        httpx.Response(
            200, json=_page(data=[_alarm("A3"), _alarm("A4")], page=2, total_pages=3, has_more=True)
        ),
        httpx.Response(200, json=_page(data=[_alarm("A5")], page=3, total_pages=3, has_more=False)),
    ]
    alarms = [a async for a in client.paginate_alarms(asset_id="NP-U1-BFP-101", page_size=2)]

    assert [a.alarm_id for a in alarms] == ["A1", "A2", "A3", "A4", "A5"]
    assert route.call_count == 3


@respx.mock
async def test_paginate_alarms_stops_at_the_hard_cap_and_logs_a_warning(
    client: AlarmApiClient,
) -> None:
    route = respx.get(f"{BASE_URL}/alarms").mock(
        return_value=httpx.Response(
            200, json=_page(data=[_alarm("A1")], page=1, total_pages=100, has_more=True)
        )
    )
    with structlog.testing.capture_logs() as captured:
        alarms = [a async for a in client.paginate_alarms(asset_id="x", page_size=1, max_pages=3)]

    assert len(alarms) == 3
    assert route.call_count == 3
    assert any("truncat" in str(entry).lower() for entry in captured)
