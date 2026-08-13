"""Identifier conventions (06-data-model.md §2). Readable, deterministic, stable
across reseeds -- no random UUIDs anywhere in the seed data.
"""

from __future__ import annotations

_SITE_ABBREVIATION = {
    "NorthPlant": "NP",
    "SouthPlant": "SP",
    "EastRefinery": "ER",
}


def _unit_abbreviation(unit: str) -> str:
    # "Unit 1" -> "U1"
    return "U" + unit.rsplit(" ", 1)[-1]


def asset_tag(*, tag_prefix: str, seq: int) -> str:
    """e.g. tag_prefix='BFP', seq=101 -> 'BFP101'."""
    return f"{tag_prefix}{seq}"


def asset_id(*, site: str, unit: str, tag_prefix: str, seq: int) -> str:
    """e.g. NP-U1-BFP-101."""
    return f"{_SITE_ABBREVIATION[site]}-{_unit_abbreviation(unit)}-{tag_prefix}-{seq}"


def alarm_code(*, tag_prefix: str, seq: int, measurement: str, condition: str) -> str:
    """e.g. BFP101-VIB-HH."""
    return f"{asset_tag(tag_prefix=tag_prefix, seq=seq)}-{measurement}-{condition}"


def alarm_id(*, year: int, seq: int) -> str:
    """e.g. ALM-2026-000001. `seq` is a global sequence, not per-asset."""
    return f"ALM-{year}-{seq:06d}"
