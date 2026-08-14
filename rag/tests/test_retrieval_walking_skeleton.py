"""Ingest ALM-PHIL-001, run one hybrid retrieval, build one citation -- the RAG slice
for the walking skeleton (02-phases.md Phase 2.5). Real Qdrant (in-memory, per R-01's
closed probe) and real FastEmbed models; nothing mocked. Phase 6 adds filters, rerank,
and the confidence gate on this same RetrievalService -- covered in
test_retrieval_filters_rerank_confidence.py; this file stays a minimal single-document
smoke test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client import QdrantClient

from rag.ingestion.collection import ensure_collection
from rag.ingestion.embedder import Embedder
from rag.ingestion.pipeline import ingest_document
from rag.retrieval.service import RetrievalService

DOC_PATH = Path(__file__).parent.parent / "documents" / "ALM-PHIL-001.md"
COLLECTION = "policy_chunks_walking_skeleton"


@pytest.fixture(scope="module")
def qdrant_client_with_one_document(embedder: Embedder) -> QdrantClient:
    client = QdrantClient(":memory:")
    ensure_collection(client, COLLECTION)
    ingest_document(client, embedder, DOC_PATH, collection_name=COLLECTION)
    return client


def test_ingest_produces_the_expected_chunk_count(
    qdrant_client_with_one_document: QdrantClient,
) -> None:
    count = qdrant_client_with_one_document.count(COLLECTION).count
    assert count >= 10  # every ### clause in ALM-PHIL-001.md


def test_stale_alarm_query_retrieves_clause_2_2(
    qdrant_client_with_one_document: QdrantClient, embedder: Embedder, reranker: TextCrossEncoder
) -> None:
    service = RetrievalService(
        qdrant_client_with_one_document, embedder, collection_name=COLLECTION, reranker=reranker
    )
    result = service.retrieve("What counts as a stale alarm?")

    assert result.citations
    top = result.citations[0]
    assert top.doc_id == "ALM-PHIL-001"
    assert top.clause_id == "2.2"
    assert top.score >= 0


def test_citation_renders_in_the_documented_format(
    qdrant_client_with_one_document: QdrantClient, embedder: Embedder, reranker: TextCrossEncoder
) -> None:
    service = RetrievalService(
        qdrant_client_with_one_document, embedder, collection_name=COLLECTION, reranker=reranker
    )
    result = service.retrieve("stale alarm definition")
    top = result.citations[0]
    assert top.rendered() == f'[ALM-PHIL-001 §{top.clause_id} "{top.title}" v1.0]'


def test_flood_query_retrieves_clause_2_6(
    qdrant_client_with_one_document: QdrantClient, embedder: Embedder, reranker: TextCrossEncoder
) -> None:
    service = RetrievalService(
        qdrant_client_with_one_document, embedder, collection_name=COLLECTION, reranker=reranker
    )
    result = service.retrieve("How many alarms in 10 minutes counts as a flood?")
    assert any(c.clause_id == "2.6" for c in result.citations)
