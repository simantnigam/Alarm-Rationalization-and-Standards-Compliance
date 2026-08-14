"""GET /api/health reports the MCP registry's lazy-discovery state (R-04,
02-phases.md Phase 5): "ok" once every configured server has been discovered at least
once, "degraded" (still HTTP 200 -- the copilot API process itself is up and serving)
while any server hasn't responded yet. This converts compose startup ordering from a
correctness requirement into an optimisation, per 01-architecture.md §5.3.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from copilot.graph.builder import build_graph
from copilot.llm.adapters.stub import StubLLMAdapter
from copilot.main import create_app
from copilot.mcp.registry import McpServerConfig, McpToolRegistry
from copilot.rag.service import RagService
from rag.ingestion.collection import ensure_collection
from rag.ingestion.embedder import Embedder
from rag.retrieval.service import RetrievalService

UNREACHABLE_URL = "http://127.0.0.1:1"
COLLECTION = "policy_chunks_health_test"


def _client(registry: McpToolRegistry, embedder: Embedder) -> TestClient:
    qdrant = QdrantClient(":memory:")
    ensure_collection(qdrant, COLLECTION)
    rag_service = RagService(RetrievalService(qdrant, embedder, collection_name=COLLECTION))
    graph = build_graph(registry, rag_service, StubLLMAdapter())
    app = create_app(graph=graph, registry=registry)
    return TestClient(app)


def test_health_reports_ok_when_there_is_nothing_to_discover(embedder: Embedder) -> None:
    registry = McpToolRegistry([])
    client = _client(registry, embedder)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_reports_ok_once_the_only_server_is_discovered(
    mcp_alarm_server_url: str, embedder: Embedder
) -> None:
    registry = McpToolRegistry([McpServerConfig(name="alarm-management", url=mcp_alarm_server_url)])
    await registry.discover()
    client = _client(registry, embedder)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_reports_degraded_while_a_server_has_not_been_discovered(
    embedder: Embedder,
) -> None:
    registry = McpToolRegistry([McpServerConfig(name="down", url=UNREACHABLE_URL)])
    await registry.discover()
    client = _client(registry, embedder)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["degraded_servers"] == ["down"]
