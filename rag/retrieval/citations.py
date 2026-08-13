"""Citation: a clause-level pointer into the corpus. Deliberately independent of
copilot.domain -- rag is a self-contained package usable by the standalone rag-ingest
job as well as the copilot backend (01-architecture.md §6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    title: str
    version: str
    clause_id: str
    section_path: str | None = None
    page: int | None = Field(default=None, ge=1)
    score: float
    snippet: str

    def rendered(self) -> str:
        page_part = f" p.{self.page}" if self.page is not None else ""
        return f'[{self.doc_id} §{self.clause_id}{page_part} "{self.title}" v{self.version}]'
