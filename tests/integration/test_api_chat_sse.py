"""POST /api/chat streams real tool, citation, and done SSE events (02-phases.md
Phase 2.5). Built on the same real graph proven in test_graph_walking_skeleton.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from copilot.graph.builder import build_graph
from copilot.llm.adapters.stub import StubLLMAdapter
from copilot.main import create_app
from copilot.mcp.registry import McpServerConfig, McpToolRegistry
from copilot.rag.service import RagService
from rag.ingestion.collection import ensure_collection
from rag.ingestion.embedder import Embedder
from rag.ingestion.pipeline import ingest_document
from rag.retrieval.service import RetrievalService

DOC_PATH = Path(__file__).parent.parent.parent / "rag" / "documents" / "ALM-PHIL-001.md"
COLLECTION = "policy_chunks_api_walking_skeleton"


@pytest.fixture(scope="module")
async def copilot_client(mcp_alarm_server_url: str, embedder: Embedder) -> TestClient:
    registry = McpToolRegistry([McpServerConfig(name="alarm-management", url=mcp_alarm_server_url)])
    await registry.discover()

    qdrant = QdrantClient(":memory:")
    ensure_collection(qdrant, COLLECTION)
    ingest_document(qdrant, embedder, DOC_PATH, collection_name=COLLECTION)
    rag_service = RagService(RetrievalService(qdrant, embedder, collection_name=COLLECTION))

    graph = build_graph(registry, rag_service, StubLLMAdapter())
    app = create_app(graph=graph)
    return TestClient(app)


def test_health_endpoint(copilot_client: TestClient) -> None:
    resp = copilot_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_streams_tool_citation_and_done_events(copilot_client: TestClient) -> None:
    with copilot_client.stream(
        "POST",
        "/api/chat",
        json={"question": "Boiler Feed Pump 101"},
        headers={"trace_id": "trace-api-test"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["trace_id"] == "trace-api-test"
        body = "".join(response.iter_text())

    assert "event: tool" in body
    assert "event: citation" in body
    assert "event: done" in body
    assert '"tool_name": "search_assets"' in body
    assert '"ok": true' in body
    assert '"doc_id": "ALM-PHIL-001"' in body
    assert "[stub-answer]" in body
    assert "trace-api-test" in body
