"""Loading and chunking ALM-PHIL-001.md: front matter parsed, clause boundaries never
split (07-rag-corpus.md §2). First slice for the walking skeleton (Phase 2.5); Phase 6
extends this over the full 8-document corpus.
"""

from __future__ import annotations

from pathlib import Path

from rag.ingestion.chunker import chunk_by_clause
from rag.ingestion.loader import load_markdown

DOC_PATH = Path(__file__).parent.parent / "documents" / "ALM-PHIL-001.md"


class TestLoadMarkdown:
    def test_parses_front_matter_fields(self) -> None:
        doc = load_markdown(DOC_PATH)
        assert doc.metadata.doc_id == "ALM-PHIL-001"
        assert doc.metadata.title == "Alarm Philosophy"
        assert doc.metadata.doc_type == "philosophy"
        assert doc.metadata.version == "1.0"
        assert doc.metadata.approval_status == "approved"
        assert doc.metadata.site_scope == "ALL"

    def test_body_excludes_front_matter(self) -> None:
        doc = load_markdown(DOC_PATH)
        assert "doc_id:" not in doc.body
        assert "# Alarm Philosophy" in doc.body

    def test_sha256_is_stable_for_identical_content(self) -> None:
        a = load_markdown(DOC_PATH)
        b = load_markdown(DOC_PATH)
        assert a.sha256 == b.sha256
        assert len(a.sha256) == 64


class TestChunkByClause:
    def test_splits_on_clause_headings(self) -> None:
        doc = load_markdown(DOC_PATH)
        chunks = chunk_by_clause(doc.body)
        clause_ids = [c.clause_id for c in chunks]
        assert "2.2" in clause_ids
        assert "2.6" in clause_ids
        assert "3.1" in clause_ids

    def test_stale_clause_content_is_self_contained(self) -> None:
        doc = load_markdown(DOC_PATH)
        chunks = chunk_by_clause(doc.body)
        stale = next(c for c in chunks if c.clause_id == "2.2")
        assert "24 hours" in stale.text
        assert stale.title == "Stale Alarm"

    def test_section_path_tracks_the_enclosing_heading(self) -> None:
        doc = load_markdown(DOC_PATH)
        chunks = chunk_by_clause(doc.body)
        stale = next(c for c in chunks if c.clause_id == "2.2")
        assert "Definitions" in stale.section_path

    def test_no_chunk_spans_more_than_one_clause(self) -> None:
        doc = load_markdown(DOC_PATH)
        chunks = chunk_by_clause(doc.body)
        for chunk in chunks:
            assert chunk.text.count("### ") == 0  # never swallows the next heading
