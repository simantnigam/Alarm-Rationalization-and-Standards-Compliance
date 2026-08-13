"""AlarmApiClient.search_assets: auth header injection, response parsing, and basic
error mapping. Phase 3 extends this connector with retry/pagination/timeout/trace-header
tests for every endpoint; this is the first slice, built for the walking skeleton
(02-phases.md Phase 2.5) and re-used unmodified by Phase 3.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from connectors.alarm_api.client import AlarmApiClient
from connectors.alarm_api.errors import AuthError, UpstreamTimeoutError, UpstreamUnavailableError

BASE_URL = "http://alarm-api:8000"


@pytest.fixture
def client() -> AlarmApiClient:
    return AlarmApiClient(base_url=BASE_URL, token="demo-token")


@respx.mock
async def test_search_assets_sends_bearer_token(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "asset_id": "NP-U1-BFP-101",
                        "asset_name": "Boiler Feed Pump 101",
                        "asset_type": "pump",
                        "site": "NorthPlant",
                        "unit": "Unit 1",
                        "criticality": "critical",
                    }
                ],
                "total": 1,
                "query": "Boiler Feed Pump 101",
                "limit": 10,
                "meta": {"request_id": "req-1", "trace_id": "trace-1"},
            },
        )
    )
    result = await client.search_assets(query="Boiler Feed Pump 101", limit=10)

    assert route.calls.last.request.headers["Authorization"] == "Bearer demo-token"
    assert result.results[0].asset_id == "NP-U1-BFP-101"
    assert result.total == 1


@respx.mock
async def test_search_assets_forwards_trace_id_header_when_given(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(
            200, json={"results": [], "total": 0, "query": "x", "limit": 20, "meta": {}}
        )
    )
    await client.search_assets(query="x", trace_id="trace-propagation-test")

    assert route.calls.last.request.headers["trace_id"] == "trace-propagation-test"


@respx.mock
async def test_search_assets_omits_trace_id_header_when_not_given(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(
            200, json={"results": [], "total": 0, "query": "x", "limit": 20, "meta": {}}
        )
    )
    await client.search_assets(query="x")

    assert "trace_id" not in route.calls.last.request.headers


@respx.mock
async def test_search_assets_parses_optional_filters_into_query_params(
    client: AlarmApiClient,
) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(
            200, json={"results": [], "total": 0, "query": "motor", "limit": 5, "meta": {}}
        )
    )
    await client.search_assets(query="motor", limit=5, unit="Unit 5")

    sent = route.calls.last.request.url.params
    assert sent["query"] == "motor"
    assert sent["unit"] == "Unit 5"
    assert sent["limit"] == "5"


@respx.mock
async def test_401_maps_to_auth_error_without_leaking_token(client: AlarmApiClient) -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(401, json={}))

    with pytest.raises(AuthError) as exc_info:
        await client.search_assets(query="x")
    assert "demo-token" not in str(exc_info.value)


@respx.mock
async def test_5xx_maps_to_upstream_unavailable(client: AlarmApiClient) -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(500, json={}))

    with pytest.raises(UpstreamUnavailableError):
        await client.search_assets(query="x")


@respx.mock
async def test_timeout_maps_to_upstream_timeout(client: AlarmApiClient) -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(side_effect=httpx.ConnectTimeout("boom"))

    with pytest.raises(UpstreamTimeoutError):
        await client.search_assets(query="x")
