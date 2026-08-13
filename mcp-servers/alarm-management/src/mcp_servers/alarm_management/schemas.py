"""Typed MCP tool I/O schemas. Distinct from connectors.alarm_api.models: this is the
MCP-level contract exposed to the copilot, not the wire contract with the Alarm API.
"""

from __future__ import annotations

from pydantic import BaseModel


class AssetResult(BaseModel):
    asset_id: str
    asset_name: str
    asset_type: str
    site: str
    unit: str
    criticality: str


class SearchAssetsOutput(BaseModel):
    results: list[AssetResult]
    total: int
    # Echoes the Alarm API simulator's own echoed trace_id (from its response `meta`
    # block), so trace propagation end to end -- GUI -> copilot -> MCP _meta -> HTTP
    # header -> simulator -> response -> here -- is assertable in one field, not just
    # claimed (01-architecture.md §3).
    simulator_trace_id: str | None = None
