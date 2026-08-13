"""Pure aggregation logic behind /alarms/summary, /trends, /correlation,
/flood-analysis, /rationalization-candidates. Hand-crafted rows so expected values are
computable by hand, not just "non-empty" (06-data-model.md §4, §7).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alarm_api_simulator.analytics.aggregation import (
    compute_candidates,
    compute_correlation,
    compute_flood_windows,
    compute_trends,
    summarize,
)
from alarm_api_simulator.timeutil import iso_z

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def _row(
    *,
    alarm_id: str,
    alarm_code: str,
    asset_id: str = "NP-U1-BFP-101",
    asset_name: str = "Boiler Feed Pump 101",
    site: str = "NorthPlant",
    unit: str = "Unit 1",
    severity: str = "high",
    is_sif_related: bool = False,
    start_time: datetime,
    duration_s: float | None = 60.0,
    ack_delay_s: float | None = 30.0,
    status: str = "cleared",
) -> dict:
    return {
        "alarm_id": alarm_id,
        "alarm_code": alarm_code,
        "asset_id": asset_id,
        "asset_name": asset_name,
        "site": site,
        "unit": unit,
        "alarm_name": "Test Alarm",
        "alarm_type": "process",
        "severity": severity,
        "is_sif_related": is_sif_related,
        "start_time": start_time,
        "end_time": None if duration_s is None else start_time + timedelta(seconds=duration_s),
        "ack_time": None if ack_delay_s is None else start_time + timedelta(seconds=ack_delay_s),
        "status": status,
        "duration_s": duration_s,
        "ack_delay_s": ack_delay_s,
        "value_at_activation": 10.0,
        "setpoint": 5.0,
        "operator_id": "OP-1",
    }


class TestSummarize:
    def test_grouped_by_severity(self) -> None:
        rows = [
            _row(alarm_id="A1", alarm_code="C1", severity="high", start_time=NOW),
            _row(alarm_id="A2", alarm_code="C1", severity="high", start_time=NOW),
            _row(alarm_id="A3", alarm_code="C2", severity="critical", start_time=NOW),
        ]
        result = summarize(rows, group_by=["severity"])
        by_key = {tuple(g["key"].items()): g for g in result["groups"]}
        assert by_key[(("severity", "high"),)]["kpis"]["alarm_count"] == 2
        assert by_key[(("severity", "critical"),)]["kpis"]["alarm_count"] == 1
        assert by_key[(("severity", "critical"),)]["kpis"]["critical_count"] == 1

    def test_no_group_by_returns_single_total_group(self) -> None:
        rows = [_row(alarm_id="A1", alarm_code="C1", start_time=NOW)]
        result = summarize(rows, group_by=[])
        assert len(result["groups"]) == 1
        assert result["groups"][0]["kpis"]["alarm_count"] == 1

    def test_avg_ack_delay_ignores_unacked(self) -> None:
        rows = [
            _row(alarm_id="A1", alarm_code="C1", start_time=NOW, ack_delay_s=10.0),
            _row(alarm_id="A2", alarm_code="C1", start_time=NOW, ack_delay_s=30.0),
            _row(alarm_id="A3", alarm_code="C1", start_time=NOW, ack_delay_s=None),
        ]
        result = summarize(rows, group_by=[])
        assert result["groups"][0]["kpis"]["avg_ack_delay"] == 20.0

    def test_totals_match_ungrouped_sum(self) -> None:
        rows = [
            _row(alarm_id="A1", alarm_code="C1", severity="high", start_time=NOW),
            _row(alarm_id="A2", alarm_code="C2", severity="critical", start_time=NOW),
        ]
        result = summarize(rows, group_by=["severity"])
        assert result["totals"]["alarm_count"] == 2
        assert result["totals"]["critical_count"] == 1


class TestComputeTrends:
    def test_daily_bucket_alarm_count(self) -> None:
        day0 = datetime(2026, 8, 1, 3, tzinfo=UTC)
        day1 = datetime(2026, 8, 2, 5, tzinfo=UTC)
        rows = [
            _row(alarm_id="A1", alarm_code="C1", start_time=day0),
            _row(alarm_id="A2", alarm_code="C1", start_time=day0 + timedelta(hours=2)),
            _row(alarm_id="A3", alarm_code="C1", start_time=day1),
        ]
        result = compute_trends(rows, bucket="daily", metrics=["alarm_count"])
        series = result["series"][0]
        assert series["metric"] == "alarm_count"
        points = {p["bucket_start"]: p["value"] for p in series["points"]}
        assert points[iso_z(datetime(2026, 8, 1, tzinfo=UTC))] == 2
        assert points[iso_z(datetime(2026, 8, 2, tzinfo=UTC))] == 1

    def test_avg_ack_delay_metric(self) -> None:
        day0 = datetime(2026, 8, 1, tzinfo=UTC)
        rows = [
            _row(alarm_id="A1", alarm_code="C1", start_time=day0, ack_delay_s=10.0),
            _row(alarm_id="A2", alarm_code="C1", start_time=day0, ack_delay_s=20.0),
        ]
        result = compute_trends(rows, bucket="daily", metrics=["avg_ack_delay"])
        points = result["series"][0]["points"]
        assert points[0]["value"] == 15.0


class TestComputeCorrelation:
    def test_cooccurring_codes_within_lag_window_are_paired(self) -> None:
        base = NOW
        rows = [
            _row(alarm_id="A1", alarm_code="C1", asset_id="X1", start_time=base),
            _row(
                alarm_id="A2",
                alarm_code="C2",
                asset_id="X2",
                start_time=base + timedelta(minutes=3),
            ),
            _row(
                alarm_id="A3",
                alarm_code="C1",
                asset_id="X1",
                start_time=base + timedelta(hours=5),
            ),
            _row(
                alarm_id="A4",
                alarm_code="C2",
                asset_id="X2",
                start_time=base + timedelta(hours=5, minutes=2),
            ),
        ]
        result = compute_correlation(
            rows,
            method="cooccurrence",
            lag_window_minutes=15,
            severity_threshold="medium",
            min_support=1,
        )
        pair = result["pairs"][0]
        assert {pair["alarm_code_a"], pair["alarm_code_b"]} == {"C1", "C2"}
        assert pair["cooccurrence_count"] == 2

    def test_min_support_filters_out_weak_pairs(self) -> None:
        rows = [
            _row(alarm_id="A1", alarm_code="C1", start_time=NOW),
            _row(alarm_id="A2", alarm_code="C2", start_time=NOW + timedelta(minutes=1)),
        ]
        result = compute_correlation(
            rows,
            method="cooccurrence",
            lag_window_minutes=15,
            severity_threshold="medium",
            min_support=5,
        )
        assert result["pairs"] == []


class TestComputeFloodWindows:
    def test_detects_a_dense_burst(self) -> None:
        base = NOW
        rows = [
            _row(alarm_id=f"A{i}", alarm_code="C1", start_time=base + timedelta(seconds=30 * i))
            for i in range(15)
        ]
        result = compute_flood_windows(rows, threshold_count=10, rolling_window_minutes=10)
        assert len(result["flood_windows"]) == 1
        window = result["flood_windows"][0]
        assert window["alarm_count"] > 10
        assert window["start"] <= iso_z(rows[0]["start_time"])

    def test_no_burst_returns_empty(self) -> None:
        rows = [
            _row(alarm_id="A1", alarm_code="C1", start_time=NOW),
            _row(alarm_id="A2", alarm_code="C1", start_time=NOW + timedelta(hours=5)),
        ]
        result = compute_flood_windows(rows, threshold_count=10, rolling_window_minutes=10)
        assert result["flood_windows"] == []


class TestComputeCandidates:
    def test_recurring_code_is_a_candidate(self) -> None:
        rows = [
            _row(alarm_id=f"A{i}", alarm_code="C1", start_time=NOW - timedelta(days=i))
            for i in range(30)
        ]
        result = compute_candidates(
            rows, recurrence_threshold=25, stale_minutes_threshold=1440, now=NOW
        )
        candidate = next(c for c in result["candidates"] if c["alarm_code"] == "C1")
        assert candidate["occurrences_90d"] == 30
        assert candidate["category"] == "recurring"

    def test_stale_occurrence_produces_stale_category(self) -> None:
        rows = [
            _row(
                alarm_id="A1",
                alarm_code="C1",
                start_time=NOW - timedelta(days=1),
                duration_s=100_000.0,  # > 24h
            )
        ]
        result = compute_candidates(
            rows, recurrence_threshold=25, stale_minutes_threshold=1440, now=NOW
        )
        candidate = next(c for c in result["candidates"] if c["alarm_code"] == "C1")
        assert candidate["category"] == "stale"
        assert candidate["stale_occurrences"] == 1
        assert candidate["max_stale_minutes"] > 1440

    def test_below_every_threshold_is_not_a_candidate(self) -> None:
        rows = [_row(alarm_id="A1", alarm_code="C1", start_time=NOW, duration_s=60.0)]
        result = compute_candidates(
            rows, recurrence_threshold=25, stale_minutes_threshold=1440, now=NOW
        )
        assert not any(c["alarm_code"] == "C1" for c in result["candidates"])

    def test_occurrences_90d_is_a_fixed_lookback_independent_of_requested_range(self) -> None:
        # 07-rag-corpus.md's caught coupling defect: occurrences_90d must not silently
        # follow whatever range the caller requested.
        rows = [
            _row(alarm_id=f"A{i}", alarm_code="C1", start_time=NOW - timedelta(days=10 * i))
            for i in range(30)  # spans ~290 days back
        ]
        result = compute_candidates(
            rows, recurrence_threshold=1, stale_minutes_threshold=1440, now=NOW
        )
        candidate = next(c for c in result["candidates"] if c["alarm_code"] == "C1")
        assert candidate["occurrences"] == 30  # over the full requested range
        assert candidate["occurrences_90d"] < 30  # fixed 90-day lookback is narrower
