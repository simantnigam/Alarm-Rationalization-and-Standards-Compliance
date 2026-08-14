"""Hand-written MCP client and tool registry (D-02 -- explicitly not
langchain-mcp-adapters). Connects to N servers over http, stdio, or an in-memory
transport, discovers tools, validates arguments client-side before dispatch, and
records every invocation as a ToolInvocation.

02-phases.md Phase 5 adds on top of the Phase 2.5 walking-skeleton slice (one server,
streamable HTTP, per-call sessions (R-09)): multi-server discovery that tolerates a down
server (R-04) -- `discover()` returns after one pass across every server; a degraded
server is retried in the background via `discover_with_backoff()`, meant to run as a
task started by the process entrypoint right after the initial `discover()` so startup
never blocks on a down server -- plus a per-call timeout and a retry policy distinct
from the connector's: transport/timeout failures retry a bounded number of times, but a
tool-level error response (the RPC succeeded, the tool itself failed) never does, since
retrying the same bad input just reproduces the same error.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import jsonschema
import structlog
from jsonschema import ValidationError as JsonSchemaValidationError
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from copilot.domain.trace import ToolInvocation
from copilot.mcp.errors import ToolInputInvalid, ToolNotFound

_logger = structlog.get_logger(__name__)

SleepFn = Callable[[float], Awaitable[None]]


async def _default_sleep(delay: float) -> None:
    await asyncio.sleep(delay)


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: Literal["http", "stdio", "memory"] = "http"
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    server: FastMCP | None = None


@dataclass(frozen=True)
class _ToolEntry:
    server: str
    input_schema: dict[str, Any]


@asynccontextmanager
async def _open_session(config: McpServerConfig) -> AsyncIterator[ClientSession]:
    if config.transport == "http":
        assert config.url is not None, "transport='http' requires url"
        async with (
            streamable_http_client(config.url) as (read, write, _get_session_id),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            yield session
    elif config.transport == "stdio":
        assert config.command is not None, "transport='stdio' requires command"
        params = StdioServerParameters(
            command=config.command, args=list(config.args), env=config.env
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            yield session
    else:
        assert config.server is not None, "transport='memory' requires server"
        async with create_connected_server_and_client_session(config.server) as session:
            yield session


class McpToolRegistry:
    def __init__(
        self,
        servers: list[McpServerConfig],
        *,
        call_timeout: float = 10.0,
        max_call_attempts: int = 2,
        call_retry_delay: float = 0.25,
        discovery_backoff_base: float = 0.5,
        discovery_backoff_cap: float = 30.0,
        sleep_fn: SleepFn = _default_sleep,
    ) -> None:
        self._servers = {s.name: s for s in servers}
        self._tools: dict[str, _ToolEntry] = {}
        self._discovered: set[str] = set()
        self._call_timeout = call_timeout
        self._max_call_attempts = max_call_attempts
        self._call_retry_delay = call_retry_delay
        self._discovery_backoff_base = discovery_backoff_base
        self._discovery_backoff_cap = discovery_backoff_cap
        self._sleep_fn = sleep_fn

    @property
    def degraded(self) -> bool:
        return set(self._servers) != self._discovered

    def degraded_servers(self) -> list[str]:
        return sorted(set(self._servers) - self._discovered)

    async def discover(self) -> None:
        """One attempt against every configured server, in parallel. Never raises on a
        down server (R-04) -- failures are recorded (see `degraded`/`degraded_servers`)
        so the registry stays usable with whichever servers responded.
        """
        await asyncio.gather(*(self._discover_one(s) for s in self._servers.values()))

    async def discover_with_backoff(self, *, max_attempts: int | None = None) -> None:
        """Retry discovery for whichever servers are still degraded, with exponential
        backoff, until every server responds or `max_attempts` is exhausted. A
        connection failure is dependency unavailability and belongs here; a genuine
        configuration error is a different failure class (R-07) that this loop is not
        meant to paper over by retrying forever.
        """
        attempt = 1
        while self.degraded:
            if max_attempts is not None and attempt > max_attempts:
                return
            delay = min(
                self._discovery_backoff_base * (2 ** (attempt - 1)), self._discovery_backoff_cap
            )
            await self._sleep_fn(delay)
            pending = [s for name, s in self._servers.items() if name not in self._discovered]
            await asyncio.gather(*(self._discover_one(s) for s in pending))
            attempt += 1

    async def _discover_one(self, server: McpServerConfig) -> bool:
        try:
            async with _open_session(server) as session:
                listed = await session.list_tools()
                for tool in listed.tools:
                    self._tools[tool.name] = _ToolEntry(
                        server=server.name, input_schema=tool.inputSchema
                    )
            self._discovered.add(server.name)
            return True
        except Exception as exc:
            await _logger.awarning(
                "mcp_server_discovery_failed", server=server.name, error=str(exc)
            )
            return False

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

        for attempt in range(1, self._max_call_attempts + 1):
            try:
                result = await asyncio.wait_for(
                    self._invoke(server, tool_name, arguments, trace_id), timeout=self._call_timeout
                )
            except Exception as exc:
                if attempt < self._max_call_attempts:
                    await self._sleep_fn(self._call_retry_delay)
                    continue
                error_code = "TIMEOUT" if isinstance(exc, TimeoutError) else "TRANSPORT_ERROR"
                return ToolInvocation(
                    tool_name=tool_name,
                    server=entry.server,
                    arguments=arguments,
                    ok=False,
                    error_code=error_code,
                    error_message=str(exc) or error_code,
                    started_at=started_at,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    retry_count=attempt - 1,
                    trace_id=trace_id,
                )
            else:
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
                        retry_count=attempt - 1,
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
                    retry_count=attempt - 1,
                    trace_id=trace_id,
                )

        raise AssertionError("unreachable")  # pragma: no cover

    async def _invoke(
        self, server: McpServerConfig, tool_name: str, arguments: dict[str, Any], trace_id: str
    ) -> Any:
        async with _open_session(server) as session:
            return await session.call_tool(tool_name, arguments, meta={"trace_id": trace_id})


def _extract_error_text(result: Any) -> str:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            return str(text)
    return "tool call failed with no error detail"
