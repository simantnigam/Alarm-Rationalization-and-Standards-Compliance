"""POST /recommendations/operator-actions, POST /calculation-code/{generate,execute},
GET /analytics/kpi-definitions. The generate->execute pair is a *controlled* KPI flow
(4.5.3x): the model chooses which registered calculation to run, never what executes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestOperatorRecommendations:
    def test_returns_rationalization_record(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        listing = api_client.get(
            "/alarms", params={"asset_id": "NP-U1-BFP-101", "page_size": 1}, headers=auth_headers
        ).json()
        alarm_id = listing["data"][0]["alarm_id"]

        resp = api_client.post(
            "/recommendations/operator-actions",
            json={"alarm_id": alarm_id, "include_related": True, "include_asset_context": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["alarm_id"] == alarm_id
        assert len(body["immediate_actions"]) >= 1
        assert len(body["diagnostic_steps"]) >= 1
        assert body["rationalization_record"]["cause"]
        assert "asset_context" in body
        assert "related_alarms" in body

    def test_optional_blocks_omitted_when_flags_false(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        listing = api_client.get(
            "/alarms", params={"asset_id": "NP-U1-BFP-101", "page_size": 1}, headers=auth_headers
        ).json()
        alarm_id = listing["data"][0]["alarm_id"]

        resp = api_client.post(
            "/recommendations/operator-actions", json={"alarm_id": alarm_id}, headers=auth_headers
        )
        body = resp.json()
        assert body.get("asset_context") is None
        assert body.get("related_alarms") is None

    def test_unknown_alarm_returns_404(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/recommendations/operator-actions",
            json={"alarm_id": "ALM-2026-999999"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestControlledKpiFlow:
    def test_generate_returns_calculation_id_and_visible_code(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/calculation-code/generate",
            json={
                "calculation_type": "nuisance_alarm_score",
                "filters": {
                    "unit": "Unit 4",
                    "start_time": "2026-05-01T00:00:00Z",
                    "end_time": "2026-07-01T00:00:00Z",
                },
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["calculation_id"]
        assert body["calculation_type"] == "nuisance_alarm_score"
        assert "def" in body["code"]  # generated code is displayed before execution
        assert body["input_schema"] and body["output_schema"]

    def test_arbitrary_calculation_type_rejected(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.post(
            "/calculation-code/generate",
            json={"calculation_type": "arbitrary_code_execution", "filters": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_execute_runs_a_previously_generated_calculation(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        gen = api_client.post(
            "/calculation-code/generate",
            json={
                "calculation_type": "critical_alarm_density",
                "filters": {
                    "unit": "Unit 3",
                    "start_time": "2026-05-01T00:00:00Z",
                    "end_time": "2026-07-01T00:00:00Z",
                },
            },
            headers=auth_headers,
        ).json()

        resp = api_client.post(
            "/calculation-code/execute",
            json={
                "calculation_id": gen["calculation_id"],
                "filters": {
                    "unit": "Unit 3",
                    "start_time": "2026-05-01T00:00:00Z",
                    "end_time": "2026-07-01T00:00:00Z",
                },
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["calculation_id"] == gen["calculation_id"]
        assert body["status"] == "completed"
        assert body["result"] is not None

    @pytest.mark.parametrize(
        "calculation_type",
        ["alarm_flood_index", "operator_response_efficiency", "nuisance_alarm_score"],
    )
    def test_execute_runs_every_registered_calculation_type(
        self, calculation_type: str, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        filters = {
            "unit": "Unit 2",
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": "2026-08-13T00:00:00Z",
        }
        gen = api_client.post(
            "/calculation-code/generate",
            json={"calculation_type": calculation_type, "filters": filters},
            headers=auth_headers,
        ).json()

        resp = api_client.post(
            "/calculation-code/execute",
            json={"calculation_id": gen["calculation_id"], "filters": filters},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert isinstance(body["result"], dict)
        assert body["result"]  # non-empty result for every registered type

    def test_execute_rejects_an_unknown_calculation_id(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # The copilot cannot submit its own code -- only a calculation_id issued by
        # `generate` is ever accepted (4.5.3x constraint 2).
        resp = api_client.post(
            "/calculation-code/execute",
            json={"calculation_id": "calc-does-not-exist", "filters": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestKpiDefinitions:
    def test_lists_published_kpi_formulas(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get("/analytics/kpi-definitions", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        ids = {d["kpi_id"] for d in body["kpi_definitions"]}
        assert "nuisance_alarm_score" in ids
        nuisance = next(d for d in body["kpi_definitions"] if d["kpi_id"] == "nuisance_alarm_score")
        assert nuisance["formula"]
        assert nuisance["reference"]
