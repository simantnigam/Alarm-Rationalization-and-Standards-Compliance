"""Ingestion produces the expected chunk count and metadata (02-phases.md Phase 6 exit
gate), pinned against test-data/expected_chunks.json (07-rag-corpus.md §5). This is a
structural golden -- doc_type, site_scope, chunk_count, and clause_ids per document --
deliberately not chunk text, so wording edits don't churn the fixture; a real content or
clause-boundary change will.

Note: 07-rag-corpus.md §5 forecasts "~120-160 chunks" across the 8 documents before any
were authored; the corpus as written lands at 39 -- every clause the rule pack, the
safety override, the deliberate site conflict, and the PDF citation demo reference is
present, and no clause was padded in just to approach the forecast.
"""

from __future__ import annotations

import json
from pathlib import Path

from rag.ingestion.chunker import chunk_by_clause
from rag.ingestion.loader import extract
from rag.ingestion.pipeline import corpus_paths

DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"
GOLDEN_PATH = Path(__file__).parent.parent.parent / "test-data" / "expected_chunks.json"


def _current_chunk_summary() -> dict:
    docs = {}
    total = 0
    for path in corpus_paths(DOCUMENTS_DIR):
        doc = extract(path)
        chunks = chunk_by_clause(doc.body)
        total += len(chunks)
        docs[doc.metadata.doc_id] = {
            "doc_type": doc.metadata.doc_type,
            "site_scope": doc.metadata.site_scope,
            "chunk_count": len(chunks),
            "clause_ids": sorted(c.clause_id for c in chunks),
        }
    return {"total_chunks": total, "documents": docs}


def test_ingestion_matches_the_golden_chunk_summary() -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert _current_chunk_summary() == golden


def test_no_chunk_spans_more_than_one_clause_across_the_whole_corpus() -> None:
    for path in corpus_paths(DOCUMENTS_DIR):
        doc = extract(path)
        for chunk in chunk_by_clause(doc.body):
            assert chunk.text.count("### ") == 0, f"{doc.metadata.doc_id} §{chunk.clause_id}"
