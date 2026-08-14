"""Hybrid retrieval (01-architecture.md §6): dense + sparse prefetch with filters
applied INSIDE each prefetch, never post-fusion -- a quarantined or out-of-scope chunk
must never consume a top-k slot (verified by scripts/probe_qdrant.py) -- then
server-side RRF fusion, optional FastEmbed cross-encoder rerank, a confidence gate, and
citations. Walking-skeleton slice (02-phases.md Phase 2.5) had none of the filters,
rerank, or confidence gate; Phase 6 adds all three on this same class.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client import QdrantClient, models

from rag.ingestion.embedder import Embedder
from rag.retrieval.citations import Citation

_SNIPPET_LENGTH = 300
DEFAULT_RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


@dataclass(frozen=True)
class RetrievalResult:
    citations: list[Citation]
    # "fused score below RAG_MIN_SCORE, or fewer than RAG_MIN_CITATIONS surviving
    # chunks" (01-architecture.md §6) -- InsufficientEvidence, one level up, is the
    # copilot's decision about what to do with this signal, not the RAG layer's.
    low_confidence: bool


class RetrievalService:
    def __init__(
        self,
        client: QdrantClient,
        embedder: Embedder,
        *,
        collection_name: str = "policy_chunks",
        top_k: int = 5,
        prefetch_limit: int = 20,
        rerank_enabled: bool = True,
        reranker: TextCrossEncoder | None = None,
        min_score: float = 0.35,
        min_citations: int = 1,
        now_fn: Callable[[], date] = date.today,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name
        self._top_k = top_k
        self._prefetch_limit = prefetch_limit
        self._reranker = reranker or (
            TextCrossEncoder(DEFAULT_RERANK_MODEL) if rerank_enabled else None
        )
        self._min_score = min_score
        self._min_citations = min_citations
        self._now_fn = now_fn

    def retrieve(
        self, query: str, *, site: str | None = None, doc_type: str | None = None
    ) -> RetrievalResult:
        dense_vector = self._embedder.embed_dense([query])[0]
        sparse_vector = self._embedder.embed_sparse([query])[0]
        query_filter = self._filter(site=site, doc_type=doc_type)

        result = self._client.query_points(
            collection_name=self._collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=self._prefetch_limit,
                    filter=query_filter,
                ),
                models.Prefetch(
                    query=sparse_vector,
                    using="bm25",
                    limit=self._prefetch_limit,
                    filter=query_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=self._prefetch_limit,
            with_payload=True,
        )

        candidates: list[tuple[dict[str, Any], float]] = []
        for point in result.points:
            assert point.payload is not None
            candidates.append((point.payload, point.score))

        if self._reranker is not None and candidates:
            rerank_scores = list(self._reranker.rerank(query, [p["text"] for p, _ in candidates]))
            candidates = [
                pair
                for _, pair in sorted(
                    zip(rerank_scores, candidates, strict=True), key=lambda x: x[0], reverse=True
                )
            ]

        citations = [
            Citation(
                doc_id=payload["doc_id"],
                title=payload["clause_title"],
                version=payload["version"],
                clause_id=payload["clause_id"],
                section_path=payload.get("section_path"),
                page=payload.get("page"),
                score=fusion_score,
                snippet=payload["text"][:_SNIPPET_LENGTH],
            )
            for payload, fusion_score in candidates[: self._top_k]
        ]

        top_score = citations[0].score if citations else 0.0
        low_confidence = len(citations) < self._min_citations or top_score < self._min_score
        return RetrievalResult(citations=citations, low_confidence=low_confidence)

    def _filter(self, *, site: str | None, doc_type: str | None) -> models.Filter:
        end_of_today = datetime.combine(self._now_fn(), time.max, tzinfo=UTC)
        must: list[models.Condition] = [
            models.FieldCondition(key="injection_flag", match=models.MatchValue(value=False)),
            models.FieldCondition(
                key="effective_date", range=models.DatetimeRange(lte=end_of_today)
            ),
        ]
        if site is not None:
            must.append(
                models.FieldCondition(key="site_scope", match=models.MatchAny(any=[site, "ALL"]))
            )
        if doc_type is not None:
            must.append(
                models.FieldCondition(key="doc_type", match=models.MatchValue(value=doc_type))
            )
        return models.Filter(must=must)
