"""Standalone entrypoint: `python -m copilot`. The `copilot-api` container command.
Walking-skeleton slice (02-phases.md Phase 2.5) plus stub LLM. `registry.discover()`
below is one non-blocking pass across every configured server (R-04) -- whichever
servers are still down after it keep retrying with backoff in the background, started
by create_app()'s lifespan, so a down MCP server at container startup never blocks this
process from serving (compose ordering becomes an optimisation, not a correctness
requirement). Phase 8 adds the real LLM adapters, PostgresSaver, and the X-API-Key
dependency (A-06).
"""

from __future__ import annotations

import asyncio
import os

import uvicorn
from qdrant_client import QdrantClient

from copilot.graph.builder import build_graph
from copilot.llm.adapters.stub import StubLLMAdapter
from copilot.main import create_app
from copilot.mcp.registry import McpServerConfig, McpToolRegistry
from copilot.rag.service import RagService
from rag.ingestion.embedder import Embedder
from rag.retrieval.service import RetrievalService


def main() -> None:  # pragma: no cover -- process entrypoint, exercised via docker-compose
    mcp_alarm_url = os.environ.get("MCP_ALARM_URL", "http://alarm-mcp:9000/mcp")
    vector_store_url = os.environ.get("VECTOR_STORE_URL", "http://qdrant:6333")
    collection_alias = os.environ.get("QDRANT_COLLECTION_ALIAS", "policy_chunks")
    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")

    registry = McpToolRegistry([McpServerConfig(name="alarm-management", url=mcp_alarm_url)])
    asyncio.run(registry.discover())

    qdrant = QdrantClient(url=vector_store_url)
    embedder = Embedder(cache_dir=cache_dir)
    rag_service = RagService(RetrievalService(qdrant, embedder, collection_name=collection_alias))

    # Stub LLM until Phase 8 wires the real Anthropic/OpenAI adapters -- the walking
    # skeleton runs end to end with zero API keys, by design (D-01, D-06b).
    graph = build_graph(registry, rag_service, StubLLMAdapter())
    app = create_app(graph=graph, registry=registry)

    host = os.environ.get("COPILOT_API_HOST", "0.0.0.0")
    port = int(os.environ.get("COPILOT_API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
