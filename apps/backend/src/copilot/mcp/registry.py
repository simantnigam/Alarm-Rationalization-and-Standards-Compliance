"""Hand-written MCP client and tool registry (D-02 -- explicitly not
langchain-mcp-adapters). Connects to N servers, discovers tools, validates arguments
client-side before dispatch, and records every invocation as a ToolInvocation.

First slice for the walking skeleton (02-phases.md Phase 2.5): one server, streamable
HTTP, per-call sessions (R-09). Phase 5 adds lazy discovery with backoff, multi-server
partial-failure handling, and a stdio transport test on top of this same class.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jsonschema
from jsonschema import ValidationError as JsonSchemaValidationError
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from copilot.domain.trace import ToolInvocation
from copilot.mcp.errors import ToolInputInvalid, ToolNotFound


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    url: str


@dataclass(frozen=True)
class _ToolEntry:
    server: str
    input_schema: dict[str, Any]


class McpToolRegistry:
    def __init__(self, servers: list[McpServerConfig]) -> None:
        self._servers = {s.name: s for s in servers}
        self._tools: dict[str, _ToolEntry] = {}

    async def discover(self) -> None:
        for server in self._servers.values():
            async with (
                streamable_http_client(server.url) as (read, write, _get_session_id),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                listed = await session.list_tools()
                for tool in listed.tools:
                    self._tools[tool.name] = _ToolEntry(
                        server=server.name, input_schema=tool.inputSchema
                    )

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any], *, trace_id: str
    ) -> ToolInvocation:
        entry = self._tools.get(tool_name)
        if entry is None:
            raise ToolNotFound(tool_name)

        try:
            jsonschema.validate(arguments, entry.input_schema)
        except JsonSchemaValidationError as exc:
            raise ToolInputInvalid(tool_name, exc.message) from exc

        server = self._servers[entry.server]
        started_at = datetime.now(UTC)
        t0 = time.monotonic()

        try:
            async with (
                streamable_http_client(server.url) as (read, write, _get_session_id),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(tool_name, arguments, meta={"trace_id": trace_id})
        except Exception as exc:
            return ToolInvocation(
                tool_name=tool_name,
                server=entry.server,
                arguments=arguments,
                ok=False,
                error_code="TRANSPORT_ERROR",
                error_message=str(exc),
                started_at=started_at,
                duration_ms=(time.monotonic() - t0) * 1000,
                retry_count=0,
                trace_id=trace_id,
            )

        duration_ms = (time.monotonic() - t0) * 1000
        if result.isError:
            return ToolInvocation(
                tool_name=tool_name,
                server=entry.server,
                arguments=arguments,
                ok=False,
                error_code="TOOL_ERROR",
                error_message=_extract_error_text(result),
                started_at=started_at,
                duration_ms=duration_ms,
                retry_count=0,
                trace_id=trace_id,
            )

        return ToolInvocation(
            tool_name=tool_name,
            server=entry.server,
            arguments=arguments,
            ok=True,
            result=result.structuredContent,
            started_at=started_at,
            duration_ms=duration_ms,
            retry_count=0,
            trace_id=trace_id,
        )


def _extract_error_text(result: Any) -> str:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            return str(text)
    return "tool call failed with no error detail"
