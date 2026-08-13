"""The four registered calculation types behind the controlled KPI flow (4.5.3x): the
model chooses *which* registered calculation to run via `calculation_type`; it never
authors what executes. `generate_code` produces code for display only -- execution
always runs these trusted functions, never the displayed string.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from alarm_api_simulator.analytics.aggregation import compute_candidates, compute_flood_windows

DESCRIPTIONS = {
    "alarm_flood_index": "Ratio of flood-window minutes to total observed minutes in scope.",
    "critical_alarm_density": "Fraction of alarms in scope classified as critical severity.",
    "operator_response_efficiency": (
        "Acknowledgement efficiency against a 300s target response time."
    ),
    "nuisance_alarm_score": "Average nuisance score across rationalization candidates in scope.",
}

_RESPONSE_TARGET_S = 300.0


def generate_code(calculation_type: str, filters: dict[str, Any]) -> str:
    return (
        f"def calculate():\n"
        f"    rows = fetch_alarms(\n"
        f"        unit={filters.get('unit')!r}, site={filters.get('site')!r},\n"
        f"        start_time={filters.get('start_time')!r}, end_time={filters.get('end_time')!r},\n"
        f"    )\n"
        f"    return {calculation_type}(rows)\n"
    )


def input_schema_for(calculation_type: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "unit": {"type": ["string", "null"]},
            "site": {"type": ["string", "null"]},
            "start_time": {"type": ["string", "null"], "format": "date-time"},
            "end_time": {"type": ["string", "null"], "format": "date-time"},
        },
    }


_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "alarm_flood_index": {
        "type": "object",
        "properties": {
            "flood_window_count": {"type": "integer"},
            "total_flood_minutes": {"type": "number"},
            "flood_index": {"type": "number"},
        },
    },
    "critical_alarm_density": {
        "type": "object",
        "properties": {
            "alarm_count": {"type": "integer"},
            "critical_count": {"type": "integer"},
            "critical_density": {"type": "number"},
        },
    },
    "operator_response_efficiency": {
        "type": "object",
        "properties": {
            "avg_ack_delay_s": {"type": "number"},
            "alarm_count": {"type": "integer"},
            "efficiency_score": {"type": "number"},
        },
    },
    "nuisance_alarm_score": {
        "type": "object",
        "properties": {
            "avg_nuisance_score": {"type": "number"},
            "candidate_count": {"type": "integer"},
            "top_codes": {"type": "array"},
        },
    },
}


def output_schema_for(calculation_type: str) -> dict[str, Any]:
    return _OUTPUT_SCHEMAS[calculation_type]


def run_calculation(calculation_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if calculation_type == "alarm_flood_index":
        flood = compute_flood_windows(rows, threshold_count=10, rolling_window_minutes=10)
        if rows:
            span_minutes = max(
                1.0,
                (
                    max(r["start_time"] for r in rows) - min(r["start_time"] for r in rows)
                ).total_seconds()
                / 60,
            )
        else:
            span_minutes = 1.0
        return {
            "flood_window_count": len(flood["flood_windows"]),
            "total_flood_minutes": flood["total_flood_minutes"],
            "flood_index": round(flood["total_flood_minutes"] / span_minutes, 4),
        }

    if calculation_type == "critical_alarm_density":
        total = len(rows)
        critical = sum(1 for r in rows if r["severity"] == "critical")
        return {
            "alarm_count": total,
            "critical_count": critical,
            "critical_density": round(critical / total, 4) if total else 0.0,
        }

    if calculation_type == "operator_response_efficiency":
        delays = [r["ack_delay_s"] for r in rows if r["ack_delay_s"] is not None]
        avg_delay = round(sum(delays) / len(delays), 2) if delays else 0.0
        efficiency = round(min(1.0, _RESPONSE_TARGET_S / avg_delay), 4) if avg_delay else 1.0
        return {
            "avg_ack_delay_s": avg_delay,
            "alarm_count": len(rows),
            "efficiency_score": efficiency,
        }

    if calculation_type == "nuisance_alarm_score":
        candidates = compute_candidates(
            rows,
            recurrence_threshold=25,
            stale_minutes_threshold=1440,
            now=datetime.now(UTC),
        )["candidates"]
        if not candidates:
            return {"avg_nuisance_score": 0.0, "candidate_count": 0, "top_codes": []}
        avg_score = round(sum(c["nuisance_score"] for c in candidates) / len(candidates), 2)
        top = sorted(candidates, key=lambda c: c["nuisance_score"], reverse=True)[:5]
        return {
            "avg_nuisance_score": avg_score,
            "candidate_count": len(candidates),
            "top_codes": [
                {"alarm_code": c["alarm_code"], "nuisance_score": c["nuisance_score"]} for c in top
            ],
        }

    raise ValueError(f"unknown calculation_type: {calculation_type!r}")
