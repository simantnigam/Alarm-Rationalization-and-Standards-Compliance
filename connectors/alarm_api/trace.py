"""TraceContext: trace_id / x-client-id / x-metadata-tag propagate on every request
this connector makes (01-architecture.md §4, §9)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceContext:
    trace_id: str | None = None
    client_id: str | None = None
    metadata_tag: str | None = None

    def headers(self) -> dict[str, str]:
        headers = {}
        if self.trace_id:
            headers["trace_id"] = self.trace_id
        if self.client_id:
            headers["x-client-id"] = self.client_id
        if self.metadata_tag:
            headers["x-metadata-tag"] = self.metadata_tag
        return headers
