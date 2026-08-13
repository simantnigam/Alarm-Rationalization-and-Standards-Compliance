"""Qdrant collection lifecycle. Named dense + sparse vectors in one collection, per the
probed pattern in scripts/probe_qdrant.py (R-01, closed against qdrant-client 1.19.0).
"""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from rag.ingestion.embedder import DENSE_DIM


def ensure_collection(client: QdrantClient, name: str) -> None:
    if client.collection_exists(name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": models.VectorParams(size=DENSE_DIM, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={"bm25": models.SparseVectorParams()},
    )
