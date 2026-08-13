"""The 8 remaining connector methods (summary/trends/flood/candidates/correlation/
recommendations/kpi generate+execute) -- each a thin POST wrapper reusing the retry,
trace, and error-mapping machinery already proven in test_connector_search_assets.py.
Happy-path + response-parsing only; the cross-cutting behavior isn't re-tested here.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from connectors.alarm_api.client import AlarmApiClient

BASE_URL = "http://alarm-api:8000"


@pytest.fixture
def client() -> AlarmApiClient:
    return AlarmApiClient(base_url=BASE_URL, token="demo-token")


@respx.mock
async def test_get_alarm_summary(client: AlarmApiClient) -> None:
    route = respx.post(f"{BASE_URL}/alarms/summary").mock(
        return_value=httpx.Response(
            200,
            json={
                "groups": [{"key": {"severity": "high"}, "kpis": {"alarm_count": 12}}],
                "totals": {"alarm_count": 12},
                "time_range": {
                    "start_time": "2026-05-01T00:00:00Z",
                    "end_time": "2026-07-01T00:00:00Z",
                },
                "meta": {},
            },
        )
    )
    result = await client.get_alarm_summary(asset_ids=["NP-U1-BFP-101"], group_by=["severity"])

    assert result.groups[0].kpis["alarm_count"] == 12
    body = route.calls.last.request.content
    assert b"NP-U1-BFP-101" in body


@respx.mock
async def test_get_alarm_trends(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/alarms/trends").mock(
        return_value=httpx.Response(
            200,
            json={
                "bucket": "daily",
                "series": [
                    {
                        "metric": "alarm_count",
                        "points": [{"bucket_start": "2026-05-01T00:00:00Z", "value": 5}],
                    }
                ],
                "meta": {},
            },
        )
    )
    result = await client.get_alarm_trends(asset_ids=["x"], bucket="daily", metrics=["alarm_count"])

    assert result.bucket == "daily"
    assert result.series[0].points[0].value == 5


@respx.mock
async def test_analyze_alarm_flood(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/alarms/flood-analysis").mock(
        return_value=httpx.Response(
            200,
            json={
                "flood_windows": [
                    {
                        "start": "2026-06-01T00:00:00Z",
                        "end": "2026-06-01T00:10:00Z",
                        "unit": "Unit 2",
                        "alarm_count": 15,
                        "peak_rate_per_10min": 15,
                        "top_contributors": [{"alarm_code": "X-1", "count": 15}],
                    }
                ],
                "threshold_count": 10,
                "rolling_window_minutes": 10,
                "total_flood_minutes": 10.0,
                "meta": {},
            },
        )
    )
    result = await client.analyze_alarm_flood(
        unit="Unit 2", threshold_count=10, rolling_window_minutes=10
    )

    assert len(result.flood_windows) == 1
    assert result.flood_windows[0].alarm_count == 15


@respx.mock
async def test_get_rationalization_candidates(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/alarms/rationalization-candidates").mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "alarm_code": "BFP101-VIB-HH",
                        "asset_id": "NP-U1-BFP-101",
                        "asset_name": "Boiler Feed Pump 101",
                        "site": "NorthPlant",
                        "unit": "Unit 1",
                        "severity": "high",
                        "is_sif_related": False,
                        "safety_classification": "none",
                        "occurrences": 30,
                        "occurrences_90d": 30,
                        "occurrences_per_day": 0.33,
                        "stale_occurrences": 0,
                        "max_stale_minutes": 0.0,
                        "chatter_index": 2,
                        "fleeting_count": 0,
                        "fleeting_rate": 0.0,
                        "avg_ack_delay_s": 45.0,
                        "max_ack_delay_s": 120.0,
                        "unacknowledged_rate": 0.1,
                        "nuisance_score": 62.0,
                        "category": "recurring",
                        "reason": "recurring",
                    }
                ],
                "total": 1,
                "meta": {},
            },
        )
    )
    result = await client.get_rationalization_candidates(asset_ids=["NP-U1-BFP-101"])

    assert result.total == 1
    assert result.candidates[0].category == "recurring"


@respx.mock
async def test_correlate_alarms(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/alarms/correlation").mock(
        return_value=httpx.Response(
            200,
            json={
                "pairs": [
                    {
                        "alarm_code_a": "A",
                        "alarm_code_b": "B",
                        "asset_a": "x1",
                        "asset_b": "x2",
                        "cooccurrence_count": 4,
                        "support": 0.5,
                        "confidence": 0.8,
                        "avg_lag_seconds": 30.0,
                        "direction": "a_leads_b",
                    }
                ],
                "method": "cooccurrence",
                "params": {},
                "meta": {},
            },
        )
    )
    result = await client.correlate_alarms(asset_ids=["x1", "x2"])

    assert result.pairs[0].cooccurrence_count == 4


@respx.mock
async def test_get_operator_recommendations(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/recommendations/operator-actions").mock(
        return_value=httpx.Response(
            200,
            json={
                "alarm_id": "ALM-2026-000001",
                "alarm_code": "BFP101-VIB-HH",
                "immediate_actions": ["Verify reading"],
                "diagnostic_steps": ["Inspect pump"],
                "rationalization_record": {
                    "cause": "Bearing wear",
                    "consequence": "Pump trip",
                    "corrective_action": "Inspect",
                    "allowable_response_time_s": 600,
                },
                "meta": {},
            },
        )
    )
    result = await client.get_operator_recommendations(alarm_id="ALM-2026-000001")

    assert result.rationalization_record.cause == "Bearing wear"


@respx.mock
async def test_generate_kpi_calculation(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/calculation-code/generate").mock(
        return_value=httpx.Response(
            200,
            json={
                "calculation_id": "calc-1",
                "calculation_type": "nuisance_alarm_score",
                "code": "def calculate(): ...",
                "language": "python",
                "description": "desc",
                "input_schema": {},
                "output_schema": {},
                "created_at": "2026-08-13T00:00:00Z",
                "meta": {},
            },
        )
    )
    result = await client.generate_kpi_calculation(calculation_type="nuisance_alarm_score")

    assert result.calculation_id == "calc-1"


@respx.mock
async def test_execute_kpi_calculation(client: AlarmApiClient) -> None:
    respx.post(f"{BASE_URL}/calculation-code/execute").mock(
        return_value=httpx.Response(
            200,
            json={
                "calculation_id": "calc-1",
                "calculation_type": "nuisance_alarm_score",
                "status": "completed",
                "result": {"avg_nuisance_score": 42.0},
                "row_count": 10,
                "duration_ms": 12.3,
                "executed_at": "2026-08-13T00:00:01Z",
                "meta": {},
            },
        )
    )
    result = await client.execute_kpi_calculation(calculation_id="calc-1")

    assert result.status == "completed"
    assert result.result["avg_nuisance_score"] == 42.0
