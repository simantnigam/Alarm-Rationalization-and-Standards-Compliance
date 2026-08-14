"""Thin client over rag/retrieval (01-architecture.md §2). No retrieval logic lives
here -- this module's only job is to adapt rag.retrieval.citations.Citation (the
package-independent wire shape) into copilot.domain.citation.Citation (the copilot's
own shared vocabulary), so the rag package stays usable standalone (e.g. by the
rag-ingest job) without depending on copilot at all.
"""

from __future__ import annotations

from copilot.domain.citation import Citation as DomainCitation
from rag.retrieval.service import RetrievalService


class RagService:
    def __init__(self, retrieval: RetrievalService) -> None:
        self._retrieval = retrieval

    def retrieve(self, query: str) -> list[DomainCitation]:
        return [
            DomainCitation(
                doc_id=c.doc_id,
                title=c.title,
                version=c.version,
                clause_id=c.clause_id,
                section_path=c.section_path,
                page=c.page,
                score=c.score,
                snippet=c.snippet,
            )
            for c in self._retrieval.retrieve(query).citations
        ]
