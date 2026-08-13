"""POST /alarms/{summary,trends,correlation,flood-analysis,rationalization-candidates}
and POST /alarms/priority-score against the real seeded compact dataset.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

START = "2026-05-01T00:00:00Z"
END = "2026-07-01T00:00:00Z"


class TestSummary:
    def test_grouped_summary_for_bfp101(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/alarms/summary",
            json={
                "asset_ids": ["NP-U1-BFP-101"],
                "time_range": {"start_time": START, "end_time": END},
                "severity": ["high", "critical"],
                "group_by": ["alarm_name"],
                "kpis": ["alarm_count", "recurring_rate", "avg_ack_delay"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "groups" in body and "totals" in body and "time_range" in body
        assert set(body["groups"][0]["kpis"]) == {"alarm_count", "recurring_rate", "avg_ack_delay"}

    def test_unknown_group_by_returns_422(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/alarms/summary", json={"group_by": ["not_a_real_field"]}, headers=auth_headers
        )
        assert resp.status_code == 422


class TestTrends:
    def test_daily_trends_for_asset(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/alarms/trends",
            json={
                "asset_ids": ["NP-U1-BFP-101"],
                "time_range": {"start_time": START, "end_time": END},
                "bucket": "daily",
                "metrics": ["alarm_count", "avg_ack_delay"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["bucket"] == "daily"
        assert {s["metric"] for s in body["series"]} == {"alarm_count", "avg_ack_delay"}


class TestCorrelation:
    def test_correlation_for_compressors(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        assets_resp = api_client.get(
            "/assets/search", params={"query": "compressor", "unit": "Unit 3"}, headers=auth_headers
        ).json()
        asset_ids = [a["asset_id"] for a in assets_resp["results"][:3]]

        resp = api_client.post(
            "/alarms/correlation",
            json={
                "asset_ids": asset_ids,
                "time_range": {"start_time": START, "end_time": END},
                "correlation_method": "cooccurrence",
                "lag_window_minutes": 15,
                "severity_threshold": "medium",
                "min_support": 1,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "pairs" in body
        assert body["method"] == "cooccurrence"


class TestFloodAnalysis:
    def test_unit2_flood_windows_pinned_start_end(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/alarms/flood-analysis",
            json={
                "unit": "Unit 2",
                "time_range": {"start_time": "2025-01-01T00:00:00Z", "end_time": END},
                "threshold_count": 10,
                "rolling_window_minutes": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["flood_windows"]) >= 1
        window = body["flood_windows"][0]
        assert "start" in window and "end" in window
        assert window["alarm_count"] > 10


class TestRationalizationCandidates:
    def test_bfp101_produces_a_recurring_candidate(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/alarms/rationalization-candidates",
            json={
                "asset_ids": ["NP-U1-BFP-101"],
                "time_range": {"start_time": "2025-01-01T00:00:00Z", "end_time": END},
                "recurrence_threshold": 5,
                "stale_minutes_threshold": 180,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert all("category" in c and "reason" in c for c in body["candidates"])
        assert all(
            c["category"] in {"stale", "recurring", "nuisance", "chattering", "fleeting"}
            for c in body["candidates"]
        )


class TestPriorityScore:
    def test_returns_score_with_factors(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        listing = api_client.get(
            "/alarms", params={"asset_id": "NP-U1-BFP-101", "page_size": 1}, headers=auth_headers
        ).json()
        alarm_id = listing["data"][0]["alarm_id"]

        resp = api_client.post(
            "/alarms/priority-score", json={"alarm_id": alarm_id}, headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert 0 <= body["priority_score"] <= 100
        assert body["alarm_id"] == alarm_id
        assert len(body["factors"]) >= 3

    def test_unknown_alarm_returns_404(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/alarms/priority-score", json={"alarm_id": "ALM-2026-999999"}, headers=auth_headers
        )
        assert resp.status_code == 404
