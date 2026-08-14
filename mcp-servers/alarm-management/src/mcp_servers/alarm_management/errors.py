"""Upstream AlarmApiError -> MCP tool error mapping (01-architecture.md §5.1's 7-row
table). FastMCP's CallToolResult.isError only carries free text (no structured code
field) -- so the code lives as a stable, parseable "CODE: detail" prefix on the
ToolError's own message. FastMCP then wraps whatever a tool raises as
`ToolError(f"Error executing tool {name}: {original}")` (mcp/server/fastmcp/tools/base.py
Tool.run) before it becomes the final CallToolResult text, so callers must search for
the code within the message, not assume it's a prefix of the whole thing. Phase 5's
client-side error_code extraction (currently a "TOOL_ERROR" placeholder in
copilot/mcp/registry.py) does that parsing -- not in scope here.
"""

from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from connectors.alarm_api.errors import (
    AlarmApiError,
    AuthError,
    ContractViolationError,
    NotFoundError,
    RateLimitError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from connectors.alarm_api.errors import ValidationError as UpstreamValidationError


def map_error(exc: AlarmApiError) -> ToolError:
    if isinstance(exc, AuthError):
        return ToolError(f"UPSTREAM_AUTH_FAILED: {exc}")
    if isinstance(exc, NotFoundError):
        return ToolError(f"RESOURCE_NOT_FOUND: {exc}")
    if isinstance(exc, UpstreamValidationError):
        return ToolError(f"INVALID_ARGUMENT: {exc}")
    if isinstance(exc, RateLimitError):
        detail = str(exc)
        if exc.retry_after is not None:
            detail = f"{detail} (retry_after={exc.retry_after})"
        return ToolError(f"RATE_LIMITED: {detail}")
    if isinstance(exc, UpstreamUnavailableError):
        return ToolError(f"UPSTREAM_UNAVAILABLE: {exc}")
    if isinstance(exc, UpstreamTimeoutError):
        return ToolError(f"UPSTREAM_TIMEOUT: {exc}")
    if isinstance(exc, ContractViolationError):
        return ToolError(f"UPSTREAM_CONTRACT_VIOLATION: {exc}")
    return ToolError(str(exc))  # pragma: no cover -- exhaustive over AlarmApiError's subclasses
