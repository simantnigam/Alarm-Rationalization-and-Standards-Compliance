"""Single-document ingestion: load -> chunk -> embed -> upsert. Walking-skeleton slice
(02-phases.md Phase 2.5) -- one document, one collection, no diffing. Phase 6 wraps this
in the full incremental (sha256 diff) + blue/green alias-swap pipeline (D-12).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from qdrant_client import QdrantClient, models

from rag.ingestion.chunker import chunk_by_clause
from rag.ingestion.embedder import Embedder
from rag.ingestion.loader import load_markdown


def _point_id(doc_id: str, clause_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}#{clause_id}"))


def ingest_document(
    client: QdrantClient, embedder: Embedder, doc_path: Path, *, collection_name: str
) -> int:
    doc = load_markdown(doc_path)
    chunks = chunk_by_clause(doc.body)
    if not chunks:
        return 0

    texts = [chunk.text for chunk in chunks]
    dense_vectors = embedder.embed_dense(texts)
    sparse_vectors = embedder.embed_sparse(texts)

    points = [
        models.PointStruct(
            id=_point_id(doc.metadata.doc_id, chunk.clause_id),
            vector={"dense": dense, "bm25": sparse},
            payload={
                "doc_id": doc.metadata.doc_id,
                "title": doc.metadata.title,
                "doc_type": doc.metadata.doc_type,
                "version": doc.metadata.version,
                "effective_date": doc.metadata.effective_date.isoformat(),
                "approval_status": doc.metadata.approval_status,
                "site_scope": doc.metadata.site_scope,
                "unit_scope": doc.metadata.unit_scope,
                "section_path": chunk.section_path,
                "clause_id": chunk.clause_id,
                "clause_title": chunk.title,
                "text": chunk.text,
                "sha256": doc.sha256,
                "injection_flag": False,
            },
        )
        for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)
