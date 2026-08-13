"""Hybrid retrieval: dense + sparse prefetch, server-side RRF fusion (D-04), citations
built from the fused top-k. Walking-skeleton slice (02-phases.md Phase 2.5) -- no
filters, no rerank, no confidence gate yet; Phase 6 adds all three on this same class.
"""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from rag.ingestion.embedder import Embedder
from rag.retrieval.citations import Citation

_SNIPPET_LENGTH = 300


class RetrievalService:
    def __init__(
        self,
        client: QdrantClient,
        embedder: Embedder,
        *,
        collection_name: str = "policy_chunks",
        top_k: int = 5,
        prefetch_limit: int = 20,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name
        self._top_k = top_k
        self._prefetch_limit = prefetch_limit

    def retrieve(self, query: str) -> list[Citation]:
        dense_vector = self._embedder.embed_dense([query])[0]
        sparse_vector = self._embedder.embed_sparse([query])[0]

        result = self._client.query_points(
            collection_name=self._collection_name,
            prefetch=[
                models.Prefetch(query=dense_vector, using="dense", limit=self._prefetch_limit),
                models.Prefetch(query=sparse_vector, using="bm25", limit=self._prefetch_limit),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=self._top_k,
            with_payload=True,
        )

        citations = []
        for point in result.points:
            # `with_payload=True` above guarantees this at runtime; the client's
            # return type just can't express that statically.
            assert point.payload is not None
            payload = point.payload
            citations.append(
                Citation(
                    doc_id=payload["doc_id"],
                    title=payload["clause_title"],
                    version=payload["version"],
                    clause_id=payload["clause_id"],
                    section_path=payload.get("section_path"),
                    score=point.score,
                    snippet=payload["text"][:_SNIPPET_LENGTH],
                )
            )
        return citations
