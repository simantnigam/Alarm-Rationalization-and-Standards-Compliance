"""Loading and chunking ALM-PHIL-001.md: front matter parsed, clause boundaries never
split (07-rag-corpus.md §2). First slice for the walking skeleton (Phase 2.5); Phase 6
extends this over the full 8-document corpus.
"""

from __future__ import annotations

from pathlib import Path

from rag.ingestion.chunker import chunk_by_clause
from rag.ingestion.loader import extract, load_markdown

DOC_PATH = Path(__file__).parent.parent / "documents" / "ALM-PHIL-001.md"
PDF_PATH = Path(__file__).parent.parent / "documents" / "ALM-STD-002.pdf"


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


class TestExtractFormatDispatch:
    """extract() (07-rag-corpus.md §5, 2.3.x traceability): `.pdf` -> pypdf page-aware
    extraction, everything else -> load_markdown(). ALM-STD-002.pdf is rendered from
    rag/documents/_source/ALM-STD-002.md by scripts/build_pdf_corpus.py.
    """

    def test_dispatches_markdown_files_to_load_markdown(self) -> None:
        doc = extract(DOC_PATH)
        assert doc.metadata.doc_id == "ALM-PHIL-001"
        assert doc.clause_pages is None

    def test_dispatches_pdf_files_to_pdf_extraction(self) -> None:
        doc = extract(PDF_PATH)
        assert doc.metadata.doc_id == "ALM-STD-002"
        assert doc.metadata.doc_type == "standard"
        assert doc.metadata.version == "1.4"

    def test_pdf_body_excludes_front_matter(self) -> None:
        doc = extract(PDF_PATH)
        assert "doc_id:" not in doc.body
        assert "Alarm Rationalization Standard" in doc.body

    def test_pdf_body_chunks_preserve_clause_boundaries(self) -> None:
        doc = extract(PDF_PATH)
        chunks = chunk_by_clause(doc.body)
        clause_ids = [c.clause_id for c in chunks]
        assert "2.3" in clause_ids
        assert "4.1" in clause_ids
        assert "4.3" in clause_ids
        for chunk in chunks:
            assert chunk.text.count("### ") == 0

    def test_pdf_clause_pages_are_captured_per_clause(self) -> None:
        doc = extract(PDF_PATH)
        assert doc.clause_pages is not None
        assert doc.clause_pages["2.3"] >= 1
        assert doc.clause_pages["4.1"] >= 1
        # 4.3 is authored well after 2.3 in the source -- it must land on a later page.
        assert doc.clause_pages["4.3"] >= doc.clause_pages["2.3"]

    def test_pdf_sha256_is_stable_and_hashes_the_pdf_bytes(self) -> None:
        a = extract(PDF_PATH)
        b = extract(PDF_PATH)
        assert a.sha256 == b.sha256
        assert len(a.sha256) == 64
