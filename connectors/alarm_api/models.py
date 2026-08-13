"""Typed response models for the Alarm Management API. Deliberately independent of
copilot.domain -- this connector models an external system's wire contract, which is
a different concern from the copilot's own shared vocabulary (01-architecture.md §6).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str | None = None
    trace_id: str | None = None
    client_id: str | None = None
    metadata_tag: str | None = None
    generated_at: str | None = None
    duration_ms: float | None = None
    sim_profile: str | None = None


class Asset(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: str
    asset_name: str
    asset_type: str
    site: str
    unit: str
    criticality: str
    service_description: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    install_date: date | None = None
    parent_asset_id: str | None = None
    tag_prefix: str | None = None


class AssetSearchResponse(BaseModel):
    results: list[Asset]
    total: int
    query: str
    limit: int
    meta: ResponseMeta
