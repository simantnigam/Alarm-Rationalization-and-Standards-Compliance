"""run_ingestion: the full incremental, blue/green pipeline (01-architecture.md §6,
07-rag-corpus.md §5) on top of pipeline.ingest_document's single-document walking-skeleton
slice. Incremental behavior and MoC gating are tested against small synthetic fixtures in
tmp_path (fast, deterministic); "every real document embeds" is tested against the
actual rag/documents/ corpus.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from qdrant_client import QdrantClient

from rag.ingestion.collection import resolve_alias
from rag.ingestion.embedder import Embedder
from rag.ingestion.pipeline import run_ingestion

REAL_DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"
REAL_DOC_IDS = {
    "ALM-PHIL-001",
    "ALM-STD-002",
    "ALM-CRIT-003",
    "SAF-INST-005",
    "SITE-POL-007",
    "SITE-POL-008",
    "SOP-BFP-014",
    "SEC-TEST-999",
}


def _write_doc(
    directory: Path,
    *,
    doc_id: str,
    clause_text: str = "Some clause text here.",
    approval_status: str = "approved",
    effective_date: str = "2020-01-01",
) -> None:
    (directory / f"{doc_id}.md").write_text(
        f"""---
doc_id: {doc_id}
title: Test Doc {doc_id}
doc_type: policy
version: "1.0"
effective_date: {effective_date}
approval_status: {approval_status}
supersedes: null
superseded_by: null
site_scope: ALL
unit_scope: ALL
owner: Test
source_note: SYNTHETIC - test fixture
---

# Test Doc {doc_id}

## 1 Section

### 1.1 Clause One

{clause_text}
""",
        encoding="utf-8",
    )


def test_full_ingestion_of_the_real_corpus_embeds_every_document(embedder: Embedder) -> None:
    client = QdrantClient(":memory:")
    summary = run_ingestion(
        client, embedder, documents_dir=REAL_DOCUMENTS_DIR, alias="real_corpus_test"
    )

    assert set(summary.embedded_docs) == REAL_DOC_IDS
    assert summary.gated_docs == []
    assert summary.total_chunks > 0
    assert summary.quarantined_chunks >= 1  # SEC-TEST-999 has at least one flagged chunk


def test_incremental_second_run_with_an_unchanged_corpus_embeds_nothing(
    tmp_path: Path, embedder: Embedder
) -> None:
    _write_doc(tmp_path, doc_id="DOC-A")
    _write_doc(tmp_path, doc_id="DOC-B")
    client = QdrantClient(":memory:")

    first = run_ingestion(client, embedder, documents_dir=tmp_path, alias="incr_test")
    assert set(first.embedded_docs) == {"DOC-A", "DOC-B"}

    second = run_ingestion(client, embedder, documents_dir=tmp_path, alias="incr_test")
    assert second.embedded_docs == []
    assert set(second.skipped_docs) == {"DOC-A", "DOC-B"}
    assert second.total_chunks == first.total_chunks


def test_changing_one_document_reembeds_only_that_document(
    tmp_path: Path, embedder: Embedder
) -> None:
    _write_doc(tmp_path, doc_id="DOC-A")
    _write_doc(tmp_path, doc_id="DOC-B")
    client = QdrantClient(":memory:")
    run_ingestion(client, embedder, documents_dir=tmp_path, alias="change_test")

    _write_doc(tmp_path, doc_id="DOC-B", clause_text="This clause text has changed.")
    second = run_ingestion(client, embedder, documents_dir=tmp_path, alias="change_test")

    assert second.embedded_docs == ["DOC-B"]
    assert second.skipped_docs == ["DOC-A"]


def test_deleting_one_document_purges_its_chunks(tmp_path: Path, embedder: Embedder) -> None:
    _write_doc(tmp_path, doc_id="DOC-A")
    _write_doc(tmp_path, doc_id="DOC-B")
    client = QdrantClient(":memory:")
    first = run_ingestion(client, embedder, documents_dir=tmp_path, alias="purge_test")
    assert first.total_chunks > 0

    (tmp_path / "DOC-B.md").unlink()
    second = run_ingestion(client, embedder, documents_dir=tmp_path, alias="purge_test")

    assert second.purged_docs == ["DOC-B"]
    collection = resolve_alias(client, "purge_test")
    assert collection is not None
    remaining_doc_ids = set()
    for point in client.scroll(collection, with_payload=True, limit=100)[0]:
        assert point.payload is not None
        remaining_doc_ids.add(point.payload["doc_id"])
    assert remaining_doc_ids == {"DOC-A"}


def test_moc_gating_excludes_a_draft_document(tmp_path: Path, embedder: Embedder) -> None:
    _write_doc(tmp_path, doc_id="DOC-DRAFT", approval_status="draft")
    client = QdrantClient(":memory:")
    summary = run_ingestion(client, embedder, documents_dir=tmp_path, alias="draft_test")

    assert summary.embedded_docs == []
    assert summary.gated_docs == ["DOC-DRAFT"]
    assert summary.total_chunks == 0


def test_moc_gating_excludes_a_future_dated_document(tmp_path: Path, embedder: Embedder) -> None:
    _write_doc(tmp_path, doc_id="DOC-FUTURE", effective_date="2099-01-01")
    client = QdrantClient(":memory:")
    summary = run_ingestion(client, embedder, documents_dir=tmp_path, alias="future_test")

    assert summary.embedded_docs == []
    assert summary.gated_docs == ["DOC-FUTURE"]


def test_moc_gating_admits_a_document_effective_exactly_today(
    tmp_path: Path, embedder: Embedder
) -> None:
    today = date(2026, 6, 1)
    _write_doc(tmp_path, doc_id="DOC-TODAY", effective_date=today.isoformat())
    client = QdrantClient(":memory:")
    summary = run_ingestion(client, embedder, documents_dir=tmp_path, alias="today_test", now=today)

    assert summary.embedded_docs == ["DOC-TODAY"]


def test_dry_run_reports_without_writing_to_qdrant(tmp_path: Path, embedder: Embedder) -> None:
    _write_doc(tmp_path, doc_id="DOC-A")
    client = QdrantClient(":memory:")

    summary = run_ingestion(
        client, embedder, documents_dir=tmp_path, alias="dry_run_test", dry_run=True
    )

    assert summary.embedded_docs == ["DOC-A"]
    assert summary.total_chunks > 0
    assert resolve_alias(client, "dry_run_test") is None
    assert client.collection_exists(summary.collection_name) is False


def test_alias_swap_is_atomic_and_old_collection_survives_for_rollback(
    tmp_path: Path, embedder: Embedder
) -> None:
    _write_doc(tmp_path, doc_id="DOC-A")
    client = QdrantClient(":memory:")
    first = run_ingestion(client, embedder, documents_dir=tmp_path, alias="atomic_test")
    old_collection = first.collection_name

    _write_doc(tmp_path, doc_id="DOC-A", clause_text="Changed content for the second run.")
    second = run_ingestion(client, embedder, documents_dir=tmp_path, alias="atomic_test")

    assert second.collection_name != old_collection
    # The old collection is untouched -- a query against it (what an in-flight request
    # started before the swap would still be reading from) still sees the old content.
    assert client.collection_exists(old_collection) is True
    old_points, _ = client.scroll(old_collection, with_payload=True, limit=10)
    assert old_points[0].payload is not None
    assert "Some clause text here." in old_points[0].payload["text"]

    assert resolve_alias(client, "atomic_test") == second.collection_name
