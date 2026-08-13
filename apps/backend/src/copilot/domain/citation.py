"""Citation: a clause-level pointer into the RAG corpus, validated against the retrieved
set before it ever reaches the GUI (Phase 6 citation validator).
"""

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
    score: float = Field(ge=0, le=1)
    snippet: str

    def rendered(self) -> str:
        """Renders as `[DOC §clause "Title" vVERSION]`, with `p.N` inserted for PDF
        sources that carry a page number.
        """
        page_part = f" p.{self.page}" if self.page is not None else ""
        return f'[{self.doc_id} §{self.clause_id}{page_part} "{self.title}" v{self.version}]'
