"""MCP client error taxonomy (01-architecture.md §5.3)."""

from __future__ import annotations


class McpClientError(Exception):
    """Base class for every error the MCP client raises."""


class ToolNotFound(McpClientError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(f"no registered tool named {tool_name!r}")
        self.tool_name = tool_name


class ToolInputInvalid(McpClientError):
    """Client-side jsonschema validation failed -- the call never reached the network."""

    def __init__(self, tool_name: str, detail: str) -> None:
        super().__init__(f"invalid arguments for {tool_name!r}: {detail}")
        self.tool_name = tool_name
        self.detail = detail
