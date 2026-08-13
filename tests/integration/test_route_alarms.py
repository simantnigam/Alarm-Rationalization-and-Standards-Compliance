"""GET /alarms (pinned: body.data[0].alarm_id) and GET /alarms/{id}. Pagination,
sorting, and the `sort_by`/`sort_order` allowlist (ORDER BY can't be parameterized).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestListAlarms:
    def test_requires_auth(self, api_client: TestClient) -> None:
        assert api_client.get("/alarms").status_code == 401

    def test_default_pagination_envelope(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get("/alarms", params={"asset_id": "NP-U1-BFP-101"}, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 50
        assert body["total"] >= 1
        assert body["total_pages"] >= 1
        assert "has_more" in body
        assert body["data"][0]["alarm_id"].startswith("ALM-")

    def test_filters_by_unit(self, api_client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = api_client.get("/alarms", params={"unit": "Unit 2"}, headers=auth_headers)
        body = resp.json()
        assert all(row["unit"] == "Unit 2" for row in body["data"])

    def test_filters_by_status_active(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get(
            "/alarms", params={"site": "EastRefinery", "status": "active"}, headers=auth_headers
        )
        body = resp.json()
        assert body["total"] >= 1
        assert all(row["status"] == "active" for row in body["data"])

    def test_pagination_page_2_is_disjoint_from_page_1(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        params = {
            "unit": "Unit 4",
            "page_size": 10,
            "sort_by": "start_time",
            "sort_order": "desc",
        }
        page1 = api_client.get("/alarms", params={**params, "page": 1}, headers=auth_headers).json()
        page2 = api_client.get("/alarms", params={**params, "page": 2}, headers=auth_headers).json()
        ids1 = {row["alarm_id"] for row in page1["data"]}
        ids2 = {row["alarm_id"] for row in page2["data"]}
        assert ids1.isdisjoint(ids2)

    def test_sort_order_ascending_vs_descending(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        asc = api_client.get(
            "/alarms",
            params={
                "unit": "Unit 3",
                "sort_by": "start_time",
                "sort_order": "asc",
                "page_size": 50,
            },
            headers=auth_headers,
        ).json()
        desc = api_client.get(
            "/alarms",
            params={
                "unit": "Unit 3",
                "sort_by": "start_time",
                "sort_order": "desc",
                "page_size": 50,
            },
            headers=auth_headers,
        ).json()
        assert asc["data"][0]["start_time"] <= asc["data"][-1]["start_time"]
        assert desc["data"][0]["start_time"] >= desc["data"][-1]["start_time"]

    def test_unknown_sort_by_rejected_not_injected(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get(
            "/alarms",
            params={"sort_by": "start_time; DROP TABLE alarms; --", "sort_order": "asc"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        # Prove the table survived.
        follow_up = api_client.get("/alarms", params={"page_size": 1}, headers=auth_headers)
        assert follow_up.status_code == 200

    def test_unknown_status_rejected(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get("/alarms", params={"status": "on_fire"}, headers=auth_headers)
        assert resp.status_code == 422


class TestGetAlarmById:
    def test_returns_alarm_with_definition(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        listing = api_client.get(
            "/alarms", params={"asset_id": "NP-U1-BFP-101", "page_size": 1}, headers=auth_headers
        ).json()
        alarm_id = listing["data"][0]["alarm_id"]

        resp = api_client.get(f"/alarms/{alarm_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["alarm_id"] == alarm_id
        assert "cause" in body["definition"]
        assert "consequence" in body["definition"]
        assert "corrective_action" in body["definition"]
        assert "allowable_response_time_s" in body["definition"]

    def test_unknown_alarm_id_returns_404(
        self, api_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = api_client.get("/alarms/ALM-2026-999999", headers=auth_headers)
        assert resp.status_code == 404
