"""GET /health (no auth) and GET /assets/search, GET /assets/{id}/metadata. The search
response shape (`results[].asset_id`) is pinned exactly by the Postman collection.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from alarm_api_simulator.config import SimulatorSettings
from alarm_api_simulator.main import create_app


class TestHealth:
    def test_health_requires_no_auth(self, api_client: TestClient) -> None:
        resp = api_client.get("/health")
        assert resp.status_code == 200

    def test_health_body_shape(self, api_client: TestClient) -> None:
        body = api_client.get("/health").json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "uptime_s" in body
        assert body["dependencies"]["database"] == "ok"
        assert body["sim_profile"] == "compact"
        assert body["seed"] == 20260812


class TestAssetsSearch:
    def test_requires_auth(self, api_client: TestClient) -> None:
        resp = api_client.get("/assets/search", params={"query": "Boiler Feed Pump 101"})
        assert resp.status_code == 401

    def test_rejects_invalid_token(self, api_client: TestClient) -> None:
        resp = api_client.get(
            "/assets/search",
            params={"query": "Boiler Feed Pump 101"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    def test_finds_boiler_feed_pump_101(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get(
            "/assets/search",
            params={"query": "Boiler Feed Pump 101", "limit": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["results"][0]["asset_id"] == "NP-U1-BFP-101"
        assert body["total"] >= 1
        assert body["meta"]["sim_profile"] == "compact"

    def test_filters_by_unit(self, api_client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = api_client.get(
            "/assets/search",
            params={"query": "motor", "unit": "Unit 5", "limit": 10},
            headers=auth_headers,
        )
        body = resp.json()
        assert body["total"] >= 3
        assert all(r["unit"] == "Unit 5" for r in body["results"])

    def test_no_match_returns_empty_results_not_error(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get(
            "/assets/search", params={"query": "nonexistent-zzz"}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_sql_injection_attempt_returns_sanitised_empty_results(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        payload = "'; DROP TABLE assets; --"
        resp = api_client.get("/assets/search", params={"query": payload}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["results"] == []
        # Prove the table survived: a normal query still works afterward.
        follow_up = api_client.get(
            "/assets/search", params={"query": "Boiler Feed Pump 101"}, headers=auth_headers
        )
        assert follow_up.json()["total"] >= 1

    def test_trace_headers_echoed_in_meta(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        headers = {
            **auth_headers,
            "trace_id": "trace-test-001",
            "x-client-id": "pytest-client",
            "x-metadata-tag": "test-run",
        }
        resp = api_client.get(
            "/assets/search", params={"query": "Boiler Feed Pump"}, headers=headers
        )
        meta = resp.json()["meta"]
        assert meta["trace_id"] == "trace-test-001"
        assert meta["client_id"] == "pytest-client"
        assert meta["metadata_tag"] == "test-run"


class TestAssetMetadata:
    def test_returns_asset_with_alarm_counts(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get("/assets/NP-U1-BFP-101/metadata", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["asset_id"] == "NP-U1-BFP-101"
        assert body["alarm_code_count"] >= 1
        assert "active_alarm_count" in body

    def test_unknown_asset_returns_404(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get("/assets/DOES-NOT-EXIST/metadata", headers=auth_headers)
        assert resp.status_code == 404


class TestFaultInjection:
    def test_500_fault_header(self, api_client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = api_client.get(
            "/assets/search",
            params={"query": "pump"},
            headers={**auth_headers, "X-Simulate-Fault": "500"},
        )
        assert resp.status_code == 500

    def test_429_fault_header_sets_retry_after(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get(
            "/assets/search",
            params={"query": "pump"},
            headers={**auth_headers, "X-Simulate-Fault": "429"},
        )
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") is not None

    def test_malformed_fault_query_param(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get(
            "/assets/search",
            params={"query": "pump", "fault": "malformed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "results" not in resp.json()

    def test_timeout_fault_exceeds_a_short_client_timeout(
        self, live_server_url: str, auth_headers: dict[str, str]
    ) -> None:
        # In-process TestClient can't enforce a real wall-clock timeout (Starlette
        # explicitly warns the `timeout` kwarg is unsupported there), so this one test
        # uses a real server over a real socket -- exactly what Phase 3's connector
        # will do against this same fault in production.
        with (
            pytest.raises(httpx.TimeoutException),
            httpx.Client(base_url=live_server_url) as client,
        ):
            client.get(
                "/assets/search",
                params={"query": "pump"},
                headers={**auth_headers, "X-Simulate-Fault": "timeout"},
                timeout=0.5,
            )


@pytest.fixture(scope="module")
def live_server_url(
    seeded_alarmdb_engine: Engine, simulator_settings: SimulatorSettings
) -> Iterator[str]:
    app = create_app(engine=seeded_alarmdb_engine, settings=simulator_settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
