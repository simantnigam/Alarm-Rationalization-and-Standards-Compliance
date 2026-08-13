"""nuisance_score and priority_score (06-data-model.md §4.1-4.2): pure, deterministic,
published via GET /analytics/kpi-definitions so the copilot can cite the formula
rather than assert the number.
"""

from __future__ import annotations

_SEVERITY_WEIGHT = {"low": 10, "medium": 40, "high": 70, "critical": 100}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def nuisance_score(
    *,
    occurrences_per_day: float,
    chatter_index: float,
    fleeting_rate: float,
    unacknowledged_rate: float,
) -> int:
    freq = _clamp(occurrences_per_day / 10, 0, 1) * 40
    chatter = _clamp(chatter_index / 6, 0, 1) * 25
    fleeting = _clamp(fleeting_rate, 0, 1) * 20
    unacked = _clamp(unacknowledged_rate, 0, 1) * 15
    return round(freq + chatter + fleeting + unacked)


def priority_score_factors(
    *,
    severity: str,
    criticality: str,
    allowable_response_time_s: float,
    is_sif_related: bool,
) -> dict:
    """Returns the score alongside its factor breakdown, so the GUI can show *why*
    rather than a bare number (06-data-model.md §5, `factors[]` on priority-score).
    """
    if severity not in _SEVERITY_WEIGHT:
        raise ValueError(f"unknown severity: {severity!r}")
    if criticality not in _SEVERITY_WEIGHT:
        raise ValueError(f"unknown criticality: {criticality!r}")
    if allowable_response_time_s <= 0:
        raise ValueError("allowable_response_time_s must be positive")

    severity_w = _SEVERITY_WEIGHT[severity] * 0.45
    criticality_w = _SEVERITY_WEIGHT[criticality] * 0.25
    urgency = _clamp(600 / allowable_response_time_s, 0, 1) * 100 * 0.30
    raw_score = round(severity_w + criticality_w + urgency)
    score = max(raw_score, 90) if is_sif_related else raw_score

    factors = [
        {
            "name": "severity",
            "value": severity,
            "weight": 0.45,
            "contribution": round(severity_w, 2),
        },
        {
            "name": "criticality",
            "value": criticality,
            "weight": 0.25,
            "contribution": round(criticality_w, 2),
        },
        {
            "name": "urgency",
            "value": allowable_response_time_s,
            "weight": 0.30,
            "contribution": round(urgency, 2),
        },
    ]
    return {"score": score, "factors": factors}


def priority_score(
    *,
    severity: str,
    criticality: str,
    allowable_response_time_s: float,
    is_sif_related: bool,
) -> int:
    result = priority_score_factors(
        severity=severity,
        criticality=criticality,
        allowable_response_time_s=allowable_response_time_s,
        is_sif_related=is_sif_related,
    )
    return int(result["score"])
