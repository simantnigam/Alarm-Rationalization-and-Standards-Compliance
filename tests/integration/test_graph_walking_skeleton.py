"""The four-node walking-skeleton graph end-to-end: real MCP tool execution against the
real simulator, real RAG citation, stub LLM synthesis (02-phases.md Phase 2.5).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from copilot.graph.builder import build_graph
from copilot.graph.state import CopilotState
from copilot.llm.adapters.stub import StubLLMAdapter
from copilot.mcp.registry import McpServerConfig, McpToolRegistry
from copilot.rag.service import RagService
from rag.ingestion.collection import ensure_collection
from rag.ingestion.embedder import Embedder
from rag.ingestion.pipeline import ingest_document
from rag.retrieval.service import RetrievalService

DOC_PATH = Path(__file__).parent.parent.parent / "rag" / "documents" / "ALM-PHIL-001.md"
COLLECTION = "policy_chunks_graph_walking_skeleton"


@pytest.fixture(scope="module")
async def compiled_graph(mcp_alarm_server_url: str, embedder: Embedder):
    registry = McpToolRegistry([McpServerConfig(name="alarm-management", url=mcp_alarm_server_url)])
    await registry.discover()

    qdrant = QdrantClient(":memory:")
    ensure_collection(qdrant, COLLECTION)
    ingest_document(qdrant, embedder, DOC_PATH, collection_name=COLLECTION)
    rag_service = RagService(RetrievalService(qdrant, embedder, collection_name=COLLECTION))

    return build_graph(registry, rag_service, StubLLMAdapter())


async def test_walking_skeleton_graph_produces_a_grounded_answer(compiled_graph) -> None:
    initial_state: CopilotState = {
        "conversation_id": "conv-1",
        "trace_id": "trace-walking-skeleton",
        "question": "Boiler Feed Pump 101",
        "plan": None,
        "invocations": [],
        "citations": [],
        "answer": "",
    }

    result = await compiled_graph.ainvoke(initial_state)

    assert result["plan"] is not None
    assert len(result["invocations"]) == 1
    invocation = result["invocations"][0]
    assert invocation.ok is True
    assert invocation.tool_name == "search_assets"
    assert invocation.trace_id == "trace-walking-skeleton"
    assert invocation.result["results"][0]["asset_id"] == "NP-U1-BFP-101"

    assert len(result["citations"]) >= 1
    assert result["citations"][0].doc_id == "ALM-PHIL-001"

    assert result["answer"].startswith("[stub-answer]")
    assert "search_assets -> ok" in result["answer"]
