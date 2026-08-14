"""Structure-aware, clause-preserving chunking (07-rag-corpus.md §2). Every clause
heading is `### {clause_id} {title}`; the chunker never splits across that boundary, so
a citation can always point at exactly one clause. `##` headings provide section_path
context but are not themselves chunk boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CLAUSE_RE = re.compile(r"^###\s+(\S+)\s+(.+)$")
_SECTION_RE = re.compile(r"^##\s+(?!#)(.+)$")


@dataclass(frozen=True)
class Chunk:
    clause_id: str
    title: str
    section_path: str
    text: str


def chunk_by_clause(body: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_section = ""
    current_clause_id: str | None = None
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_clause_id is not None:
            chunks.append(
                Chunk(
                    clause_id=current_clause_id,
                    title=current_title,
                    section_path=current_section,
                    text="\n".join(current_lines).strip(),
                )
            )

    for line in body.splitlines():
        clause_match = CLAUSE_RE.match(line)
        section_match = _SECTION_RE.match(line)
        if clause_match:
            flush()
            current_clause_id, current_title = clause_match.group(1), clause_match.group(2)
            current_lines = []
        elif section_match:
            flush()
            current_section = section_match.group(1)
            current_clause_id = None
            current_lines = []
        elif current_clause_id is not None:
            current_lines.append(line)
    flush()
    return chunks
