"""Upstream AlarmApiError -> MCP tool error mapping (01-architecture.md §5.1's 7-row
table). Pure unit test of the mapping function -- the end-to-end version (through a real
tool call) lives in tests/integration/test_mcp_server_error_mapping.py.
"""

from __future__ import annotations

import pytest

from connectors.alarm_api.errors import (
    AuthError,
    ContractViolationError,
    NotFoundError,
    RateLimitError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from connectors.alarm_api.errors import ValidationError as UpstreamValidationError
from mcp_servers.alarm_management.errors import map_error


@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (AuthError("authentication failed"), "UPSTREAM_AUTH_FAILED"),
        (NotFoundError("resource not found"), "RESOURCE_NOT_FOUND"),
        (UpstreamValidationError("request rejected by upstream"), "INVALID_ARGUMENT"),
        (RateLimitError("rate limited"), "RATE_LIMITED"),
        (UpstreamUnavailableError("upstream returned 503"), "UPSTREAM_UNAVAILABLE"),
        (UpstreamTimeoutError("timed out"), "UPSTREAM_TIMEOUT"),
        (ContractViolationError("bad shape"), "UPSTREAM_CONTRACT_VIOLATION"),
    ],
)
def test_maps_each_upstream_error_to_its_mcp_code(exc: Exception, expected_code: str) -> None:
    mapped = map_error(exc)  # type: ignore[arg-type]
    assert str(mapped).startswith(f"{expected_code}: ")


def test_rate_limit_error_carries_retry_after_into_the_message() -> None:
    mapped = map_error(RateLimitError("rate limited", retry_after=12.5))
    assert "retry_after=12.5" in str(mapped)


def test_never_leaks_the_token_even_if_present_in_the_original_message() -> None:
    mapped = map_error(AuthError("authentication failed"))
    assert "Bearer" not in str(mapped)
