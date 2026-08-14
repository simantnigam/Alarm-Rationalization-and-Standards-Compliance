"""End-to-end version of the 7-row upstream -> MCP error mapping table
(01-architecture.md §5.1), proven through a real tool call over the in-memory MCP
transport with respx mocking the connector's HTTP calls. The mapping logic itself is
unit-tested in isolation in tests/unit/test_mcp_error_mapping.py; here we prove it's
actually wired into a tool (search_assets -- the mapping is shared/tool-agnostic, so one
representative tool is sufficient, per 02-phases.md Phase 3's connector-level coverage).

`build_server`'s injectable `client` parameter is used here so the retry-exhaustion
rows (429/5xx/timeout) use tiny backoff bounds instead of the multi-second production
defaults -- same trick tests/unit/test_connector_search_assets.py uses for the
connector directly.

FastMCP wraps every tool-body exception as `ToolError(f"Error executing tool {name}:
{original}")` (mcp/server/fastmcp/tools/base.py Tool.run) before it becomes the
CallToolResult's free-text error message -- so the mapped code is *inside* the message,
not a prefix of it. Assertions here check containment, matching that reality.
"""

from __future__ import annotations

import httpx
import respx
from mcp.shared.memory import create_connected_server_and_client_session

from connectors.alarm_api.client import AlarmApiClient
from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.server import build_server

BASE_URL = "http://fake-alarm-api.test"
TOKEN = "super-secret-alarm-api-token"


def _search_response() -> dict:
    return {
        "results": [],
        "total": 0,
        "query": "pump",
        "limit": 20,
        "meta": {"trace_id": "trace-1"},
    }


def _text(result: object) -> str:
    content = getattr(result, "content")  # noqa: B009
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return str(text)
    return ""


async def _call_search_assets() -> str:
    client = AlarmApiClient(base_url=BASE_URL, token=TOKEN, backoff_base=0.001, backoff_cap=0.01)
    settings = AlarmMcpSettings(alarm_api_token=TOKEN, alarm_api_base_url=BASE_URL)
    mcp = build_server(settings, client=client)

    async with create_connected_server_and_client_session(mcp) as session:
        result = await session.call_tool("search_assets", {"query": "pump"})

    assert result.isError is True
    return _text(result)


@respx.mock
async def test_401_maps_to_upstream_auth_failed() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(401, json={}))
    text = await _call_search_assets()
    assert "UPSTREAM_AUTH_FAILED: " in text


@respx.mock
async def test_404_maps_to_resource_not_found() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(404, json={}))
    text = await _call_search_assets()
    assert "RESOURCE_NOT_FOUND: " in text


@respx.mock
async def test_422_maps_to_invalid_argument() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(422, json={}))
    text = await _call_search_assets()
    assert "INVALID_ARGUMENT: " in text


@respx.mock
async def test_429_post_retry_maps_to_rate_limited_with_retry_after() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "5"}, json={})
    )
    text = await _call_search_assets()
    assert "RATE_LIMITED: " in text
    assert "retry_after=5.0" in text


@respx.mock
async def test_5xx_post_retry_maps_to_upstream_unavailable() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(503, json={}))
    text = await _call_search_assets()
    assert "UPSTREAM_UNAVAILABLE: " in text


@respx.mock
async def test_timeout_post_retry_maps_to_upstream_timeout() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(side_effect=httpx.ConnectTimeout("boom"))
    text = await _call_search_assets()
    assert "UPSTREAM_TIMEOUT: " in text


@respx.mock
async def test_schema_mismatch_maps_to_upstream_contract_violation() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    text = await _call_search_assets()
    assert "UPSTREAM_CONTRACT_VIOLATION: " in text


@respx.mock
async def test_the_token_never_leaks_into_an_error_message() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(return_value=httpx.Response(401, json={}))
    text = await _call_search_assets()
    assert TOKEN not in text


@respx.mock
async def test_happy_path_still_returns_structured_content_not_an_error() -> None:
    respx.get(f"{BASE_URL}/assets/search").mock(
        return_value=httpx.Response(200, json=_search_response())
    )
    client = AlarmApiClient(base_url=BASE_URL, token=TOKEN, backoff_base=0.001, backoff_cap=0.01)
    settings = AlarmMcpSettings(alarm_api_token=TOKEN, alarm_api_base_url=BASE_URL)
    mcp = build_server(settings, client=client)

    async with create_connected_server_and_client_session(mcp) as session:
        result = await session.call_tool("search_assets", {"query": "pump"})

    assert result.isError is False
    assert result.structuredContent is not None
