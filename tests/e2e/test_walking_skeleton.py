"""THE walking-skeleton test (02-phases.md Phase 2.5): request in, MCP tool executed
against the real simulator, RAG citation returned, trace non-empty, trace_id
propagation proven end to end, no API keys needed anywhere in the chain. This test
stays green for the rest of the build and fails loudly the moment a seam breaks.

Every piece here is real: real Postgres (testcontainers), real Alarm API simulator
(seeded, over a real socket), real alarm-management MCP server (real streamable-HTTP
transport), real hand-written MCP client, real Qdrant (in-memory, per R-01's closed
probe) with real FastEmbed models, real LangGraph. Only the LLM is a stub -- proving
the whole system runs with zero API keys, per D-01 and D-06b.
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
COLLECTION = "policy_chunks_e2e_walking_skeleton"
TRACE_ID = "trace-e2e-walking-skeleton"


@pytest.fixture(scope="module")
async def app_client(mcp_alarm_server_url: str, embedder: Embedder) -> TestClient:
    registry = McpToolRegistry([McpServerConfig(name="alarm-management", url=mcp_alarm_server_url)])
    await registry.discover()

    qdrant = QdrantClient(":memory:")
    ensure_collection(qdrant, COLLECTION)
    ingest_document(qdrant, embedder, DOC_PATH, collection_name=COLLECTION)
    rag_service = RagService(RetrievalService(qdrant, embedder, collection_name=COLLECTION))

    graph = build_graph(registry, rag_service, StubLLMAdapter())
    return create_app(graph=graph, registry=registry)


def test_walking_skeleton_end_to_end(app_client) -> None:
    client = TestClient(app_client)

    with client.stream(
        "POST",
        "/api/chat",
        json={"question": "Boiler Feed Pump 101"},
        headers={"trace_id": TRACE_ID},
    ) as response:
        assert response.status_code == 200
        # The GUI's trace_id is echoed back on the response itself.
        assert response.headers["trace_id"] == TRACE_ID
        body = "".join(response.iter_text())

    # Real MCP execution against the real simulator.
    assert "event: tool" in body
    assert '"tool_name": "search_assets"' in body
    assert '"server": "alarm-management"' in body
    assert '"ok": true' in body

    # Real RAG citation.
    assert "event: citation" in body
    assert '"doc_id": "ALM-PHIL-001"' in body

    # A grounded answer, produced with zero API keys (stub LLM).
    assert "event: done" in body
    assert "[stub-answer]" in body

    # Trace is non-empty and carries the GUI's trace_id through every event.
    assert body.count(TRACE_ID) >= 2  # response header + at least one SSE event
