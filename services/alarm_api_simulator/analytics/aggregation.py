"""Pure aggregation functions behind the analytics endpoints. No I/O, no randomness --
given the same rows, always the same answer. This is the layer the copilot's compliance
engine ultimately depends on for measured evidence, so every metric it can predicate on
is computed here (07-rag-corpus.md §4).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from alarm_api_simulator.analytics.metrics import nuisance_score
from alarm_api_simulator.timeutil import iso_z

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_GROUP_BY_ALLOWLIST = {"alarm_name", "asset_id", "asset_name", "severity", "alarm_code"}
_SUMMARY_RECURRING_THRESHOLD = 5
_SUMMARY_SUPPRESSION_THRESHOLD = 10
_FLEETING_SECONDS = 5.0
_CHATTER_WINDOW_MINUTES = 10
_CHATTERING_CATEGORY_WINDOW_MINUTES = 1
_CHATTERING_CATEGORY_MIN_COUNT = 3
_NUISANCE_CATEGORY_THRESHOLD = 60
_FLEETING_CATEGORY_RATE = 0.3


def _group_key(row: dict[str, Any], group_by: list[str]) -> tuple[tuple[str, str], ...]:
    return tuple((field, row[field]) for field in group_by)


def _kpis_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    alarm_count = len(rows)
    ack_delays = [r["ack_delay_s"] for r in rows if r["ack_delay_s"] is not None]
    avg_ack_delay = round(sum(ack_delays) / len(ack_delays), 2) if ack_delays else 0.0
    critical_count = sum(1 for r in rows if r["severity"] == "critical")

    by_code: dict[str, int] = {}
    for r in rows:
        by_code[r["alarm_code"]] = by_code.get(r["alarm_code"], 0) + 1
    n_codes = len(by_code) or 1
    recurring_rate = round(
        sum(1 for c in by_code.values() if c >= _SUMMARY_RECURRING_THRESHOLD) / n_codes, 4
    )
    suppression_candidate_rate = round(
        sum(1 for c in by_code.values() if c >= _SUMMARY_SUPPRESSION_THRESHOLD) / n_codes, 4
    )

    return {
        "alarm_count": alarm_count,
        "recurring_rate": recurring_rate,
        "avg_ack_delay": avg_ack_delay,
        "critical_count": critical_count,
        "suppression_candidate_rate": suppression_candidate_rate,
    }


def summarize(rows: list[dict[str, Any]], *, group_by: list[str]) -> dict[str, Any]:
    unknown = set(group_by) - _GROUP_BY_ALLOWLIST
    if unknown:
        raise ValueError(f"unknown group_by field(s): {sorted(unknown)}")

    if not group_by:
        return {
            "groups": [{"key": {}, "kpis": _kpis_for_rows(rows)}],
            "totals": _kpis_for_rows(rows),
        }

    grouped: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_group_key(row, group_by), []).append(row)

    groups = [
        {"key": dict(key), "kpis": _kpis_for_rows(group_rows)}
        for key, group_rows in grouped.items()
    ]
    return {"groups": groups, "totals": _kpis_for_rows(rows)}


def _bucket_start(dt: datetime, bucket: str) -> datetime:
    if bucket == "hourly":
        return dt.replace(minute=0, second=0, microsecond=0)
    if bucket == "daily":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "weekly":
        start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day - timedelta(days=start_of_day.weekday())
    if bucket == "monthly":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"unknown bucket: {bucket!r}")


def compute_trends(
    rows: list[dict[str, Any]], *, bucket: str, metrics: list[str]
) -> dict[str, Any]:
    by_bucket: dict[datetime, list[dict[str, Any]]] = {}
    for row in rows:
        by_bucket.setdefault(_bucket_start(row["start_time"], bucket), []).append(row)

    series = []
    for metric in metrics:
        points = []
        for bucket_start in sorted(by_bucket):
            bucket_rows = by_bucket[bucket_start]
            if metric == "alarm_count":
                value: float = len(bucket_rows)
            elif metric == "avg_ack_delay":
                delays = [r["ack_delay_s"] for r in bucket_rows if r["ack_delay_s"] is not None]
                value = round(sum(delays) / len(delays), 2) if delays else 0.0
            elif metric == "critical_count":
                value = sum(1 for r in bucket_rows if r["severity"] == "critical")
            else:
                raise ValueError(f"unknown metric: {metric!r}")
            points.append({"bucket_start": iso_z(bucket_start), "value": value})
        series.append({"metric": metric, "points": points})

    return {"bucket": bucket, "series": series}


def compute_correlation(
    rows: list[dict[str, Any]],
    *,
    method: str,
    lag_window_minutes: float,
    severity_threshold: str,
    min_support: int,
) -> dict[str, Any]:
    min_severity = _SEVERITY_ORDER[severity_threshold]
    eligible = [r for r in rows if _SEVERITY_ORDER[r["severity"]] >= min_severity]
    eligible.sort(key=lambda r: r["start_time"])

    window = timedelta(minutes=lag_window_minutes)
    pair_events: dict[tuple[str, str], list[float]] = {}
    counts: dict[str, int] = {}
    asset_of: dict[str, str] = {}
    for r in eligible:
        counts[r["alarm_code"]] = counts.get(r["alarm_code"], 0) + 1
        asset_of[r["alarm_code"]] = r["asset_id"]

    for i, a in enumerate(eligible):
        for b in eligible[i + 1 :]:
            if b["start_time"] - a["start_time"] > window:
                break
            if a["alarm_code"] == b["alarm_code"]:
                continue
            code_a, code_b = sorted((a["alarm_code"], b["alarm_code"]))
            lag = (b["start_time"] - a["start_time"]).total_seconds()
            signed_lag = lag if a["alarm_code"] == code_a else -lag
            pair_events.setdefault((code_a, code_b), []).append(signed_lag)

    pairs = []
    for (code_a, code_b), lags in pair_events.items():
        cooccurrence_count = len(lags)
        if cooccurrence_count < min_support:
            continue
        denom = min(counts[code_a], counts[code_b]) or 1
        avg_lag = sum(lags) / len(lags)
        pairs.append(
            {
                "alarm_code_a": code_a,
                "alarm_code_b": code_b,
                "asset_a": asset_of[code_a],
                "asset_b": asset_of[code_b],
                "cooccurrence_count": cooccurrence_count,
                "support": round(cooccurrence_count / denom, 4),
                "confidence": round(cooccurrence_count / counts[code_a], 4),
                "avg_lag_seconds": round(avg_lag, 2),
                "direction": "a_leads_b" if avg_lag >= 0 else "b_leads_a",
            }
        )
    pairs.sort(key=lambda p: cast(int, p["cooccurrence_count"]), reverse=True)

    return {
        "pairs": pairs,
        "method": method,
        "params": {
            "lag_window_minutes": lag_window_minutes,
            "severity_threshold": severity_threshold,
            "min_support": min_support,
        },
    }


def compute_flood_windows(
    rows: list[dict[str, Any]], *, threshold_count: int, rolling_window_minutes: float
) -> dict[str, Any]:
    starts = sorted(r["start_time"] for r in rows)
    window = timedelta(minutes=rolling_window_minutes)

    dense_indices: set[int] = set()
    left = 0
    for right in range(len(starts)):
        while starts[right] - starts[left] > window:
            left += 1
        if right - left + 1 > threshold_count:
            dense_indices.update(range(left, right + 1))

    # Merge the dense indices into contiguous windows.
    flood_windows = []
    sorted_dense = sorted(dense_indices)
    i = 0
    while i < len(sorted_dense):
        j = i
        while j + 1 < len(sorted_dense) and sorted_dense[j + 1] == sorted_dense[j] + 1:
            j += 1
        idx_start, idx_end = sorted_dense[i], sorted_dense[j]
        window_start, window_end = starts[idx_start], starts[idx_end]
        window_rows = [r for r in rows if window_start <= r["start_time"] <= window_end]

        contributors: dict[str, int] = {}
        for r in window_rows:
            contributors[r["alarm_code"]] = contributors.get(r["alarm_code"], 0) + 1
        top_contributors = sorted(
            ({"alarm_code": code, "count": count} for code, count in contributors.items()),
            key=lambda c: cast(int, c["count"]),
            reverse=True,
        )[:5]

        flood_windows.append(
            {
                "start": iso_z(window_start),
                "end": iso_z(window_end),
                "unit": window_rows[0]["unit"] if window_rows else None,
                "alarm_count": len(window_rows),
                "peak_rate_per_10min": idx_end - idx_start + 1,
                "top_contributors": top_contributors,
            }
        )
        i = j + 1

    total_flood_minutes = sum(
        (
            datetime.fromisoformat(cast(str, w["end"]))
            - datetime.fromisoformat(cast(str, w["start"]))
        ).total_seconds()
        / 60
        for w in flood_windows
    )
    return {
        "flood_windows": flood_windows,
        "threshold_count": threshold_count,
        "rolling_window_minutes": rolling_window_minutes,
        "total_flood_minutes": round(total_flood_minutes, 2),
    }


def _max_count_in_any_window(starts: list[datetime], window: timedelta) -> int:
    starts = sorted(starts)
    best = 0
    left = 0
    for right in range(len(starts)):
        while starts[right] - starts[left] > window:
            left += 1
        best = max(best, right - left + 1)
    return best


def compute_candidates(
    rows: list[dict[str, Any]],
    *,
    recurrence_threshold: int,
    stale_minutes_threshold: float,
    now: datetime,
) -> dict[str, Any]:
    by_code: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_code.setdefault(r["alarm_code"], []).append(r)

    window_90d_start = now - timedelta(days=90)
    stale_seconds = stale_minutes_threshold * 60

    candidates = []
    for code, code_rows in by_code.items():
        occurrences = len(code_rows)
        occurrences_90d = sum(1 for r in code_rows if r["start_time"] >= window_90d_start)
        span_days = max(
            1.0, (now - min(r["start_time"] for r in code_rows)).total_seconds() / 86400
        )
        occurrences_per_day = round(occurrences / span_days, 3)

        durations = [r["duration_s"] for r in code_rows if r["duration_s"] is not None]
        stale_rows = [d for d in durations if d > stale_seconds]
        stale_occurrences = len(stale_rows)
        max_stale_minutes = round(max(stale_rows) / 60, 2) if stale_rows else 0.0

        chatter_index = _max_count_in_any_window(
            [r["start_time"] for r in code_rows], timedelta(minutes=_CHATTER_WINDOW_MINUTES)
        )
        chatter_1min = _max_count_in_any_window(
            [r["start_time"] for r in code_rows],
            timedelta(minutes=_CHATTERING_CATEGORY_WINDOW_MINUTES),
        )

        fleeting_count = sum(1 for d in durations if d < _FLEETING_SECONDS)
        fleeting_rate = round(fleeting_count / occurrences, 4) if occurrences else 0.0

        ack_delays = [r["ack_delay_s"] for r in code_rows if r["ack_delay_s"] is not None]
        avg_ack_delay_s = round(sum(ack_delays) / len(ack_delays), 2) if ack_delays else 0.0
        max_ack_delay_s = round(max(ack_delays), 2) if ack_delays else 0.0
        unacked = sum(1 for r in code_rows if r["ack_time"] is None)
        unacknowledged_rate = round(unacked / occurrences, 4) if occurrences else 0.0

        severity = code_rows[0]["severity"]
        is_sif_related = code_rows[0]["is_sif_related"]
        score = nuisance_score(
            occurrences_per_day=occurrences_per_day,
            chatter_index=chatter_index,
            fleeting_rate=fleeting_rate,
            unacknowledged_rate=unacknowledged_rate,
        )

        category: str | None
        reason: str
        if stale_occurrences > 0:
            category = "stale"
            reason = (
                f"{stale_occurrences} occurrence(s) exceeded the stale threshold of "
                f"{stale_minutes_threshold:.0f} minutes (max {max_stale_minutes:.0f} min)."
            )
        elif chatter_1min >= _CHATTERING_CATEGORY_MIN_COUNT:
            category = "chattering"
            reason = f"Up to {chatter_1min} occurrences observed within a single minute."
        elif fleeting_rate >= _FLEETING_CATEGORY_RATE:
            category = "fleeting"
            reason = f"{fleeting_rate:.0%} of occurrences lasted under {_FLEETING_SECONDS:.0f}s."
        elif score >= _NUISANCE_CATEGORY_THRESHOLD:
            category = "nuisance"
            reason = (
                f"Nuisance score {score} meets the nuisance threshold of "
                f"{_NUISANCE_CATEGORY_THRESHOLD}."
            )
        elif occurrences_90d >= recurrence_threshold:
            category = "recurring"
            reason = (
                f"{occurrences_90d} occurrences in the trailing 90 days meets the "
                f"recurrence threshold of {recurrence_threshold}."
            )
        else:
            category = None
            reason = ""

        if category is None:
            continue

        candidates.append(
            {
                "alarm_code": code,
                "asset_id": code_rows[0]["asset_id"],
                "asset_name": code_rows[0]["asset_name"],
                "site": code_rows[0]["site"],
                "unit": code_rows[0]["unit"],
                "severity": severity,
                "is_sif_related": is_sif_related,
                "safety_classification": "sif" if is_sif_related else "none",
                "occurrences": occurrences,
                "occurrences_90d": occurrences_90d,
                "occurrences_per_day": occurrences_per_day,
                "stale_occurrences": stale_occurrences,
                "max_stale_minutes": max_stale_minutes,
                "chatter_index": chatter_index,
                "fleeting_count": fleeting_count,
                "fleeting_rate": fleeting_rate,
                "avg_ack_delay_s": avg_ack_delay_s,
                "max_ack_delay_s": max_ack_delay_s,
                "unacknowledged_rate": unacknowledged_rate,
                "nuisance_score": score,
                "category": category,
                "reason": reason,
            }
        )

    candidates.sort(key=lambda c: float(c["nuisance_score"]), reverse=True)
    return {"candidates": candidates, "total": len(candidates)}
