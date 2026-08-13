"""AlarmApiClient.search_assets and the cross-cutting connector behaviors it exercises
first: auth, trace propagation, retry with full jitter, Retry-After, timeout/5xx
exhaustion, and malformed-response handling (02-phases.md Phase 3). Every other
endpoint method reuses this same machinery without re-testing it.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from connectors.alarm_api.client import AlarmApiClient
from connectors.alarm_api.errors import (
    AuthError,
    ContractViolationError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from connectors.alarm_api.trace import TraceContext

BASE_URL = "http://alarm-api:8000"


def _search_response(**overrides: object) -> dict:
    body = {
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
    }
    body.update(overrides)
    return body


@pytest.fixture
def client() -> AlarmApiClient:
    # Tiny backoff bounds keep the retry tests fast without mocking asyncio.sleep.
    return AlarmApiClient(
        base_url=BASE_URL, token="demo-token", backoff_base=0.001, backoff_cap=0.01
    )


@respx.mock
async def test_search_assets_sends_bearer_token(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(200, json=_search_response())
    )
    result = await client.search_assets(query="Boiler Feed Pump 101", limit=10)

    assert route.calls.last.request.headers["Authorization"] == "Bearer demo-token"
    assert result.results[0].asset_id == "NP-U1-BFP-101"
    assert result.total == 1


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
async def test_trace_context_headers_are_sent(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(200, json=_search_response())
    )
    await client.search_assets(
        query="x",
        trace=TraceContext(trace_id="trace-99", client_id="gui", metadata_tag="demo"),
    )

    sent = route.calls.last.request.headers
    assert sent["trace_id"] == "trace-99"
    assert sent["x-client-id"] == "gui"
    assert sent["x-metadata-tag"] == "demo"


@respx.mock
async def test_no_trace_context_sends_no_trace_headers(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(200, json=_search_response())
    )
    await client.search_assets(query="x")

    assert "trace_id" not in route.calls.last.request.headers


@respx.mock
async def test_401_maps_to_auth_error_without_leaking_token(client: AlarmApiClient) -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(401, json={}))

    with pytest.raises(AuthError) as exc_info:
        await client.search_assets(query="x")
    assert "demo-token" not in str(exc_info.value)


@respx.mock
async def test_malformed_response_body_raises_contract_violation(
    client: AlarmApiClient,
) -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    with pytest.raises(ContractViolationError):
        await client.search_assets(query="x")


@respx.mock
async def test_429_then_success_retries_transparently(client: AlarmApiClient) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={}),
            httpx.Response(200, json=_search_response()),
        ]
    )
    result = await client.search_assets(query="x")

    assert route.call_count == 2
    assert result.total == 1


@respx.mock
async def test_retry_after_header_is_honoured(client: AlarmApiClient) -> None:
    captured_delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        captured_delays.append(delay)

    client._sleep_fn = fake_sleep  # type: ignore[method-assign]
    respx.get(f"{BASE_URL}/assets/search").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}, json={}),
            httpx.Response(200, json=_search_response()),
        ]
    )
    await client.search_assets(query="x")

    assert captured_delays == [7.0]


@respx.mock
async def test_5xx_exhausts_retries_and_maps_to_upstream_unavailable(
    client: AlarmApiClient,
) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(503, json={}))
    with pytest.raises(UpstreamUnavailableError):
        await client.search_assets(query="x")
    assert route.call_count == client.max_attempts


@respx.mock
async def test_timeout_exhausts_retries_and_maps_to_upstream_timeout(
    client: AlarmApiClient,
) -> None:
    route = respx.get(f"{BASE_URL}/assets/search").mock(side_effect=httpx.ConnectTimeout("boom"))
    with pytest.raises(UpstreamTimeoutError):
        await client.search_assets(query="x")
    assert route.call_count == client.max_attempts
