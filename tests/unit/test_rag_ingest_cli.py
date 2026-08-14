"""scripts/rag_bootstrap.py: the rag-ingest CLI's argument parsing and its testable
`run()` core (the real `main()` reads env vars and builds a real Qdrant/Embedder, so it
stays a process entrypoint -- 02-phases.md Phase 6, "rag-ingest CLI (--full /
--incremental / --dry-run)").
"""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from scripts.rag_bootstrap import _parse_args, run

from rag.ingestion.embedder import DENSE_MODEL, Embedder


def _write_doc(directory: Path, *, doc_id: str, clause_text: str = "Some clause text.") -> None:
    (directory / f"{doc_id}.md").write_text(
        f"""---
doc_id: {doc_id}
title: Test Doc {doc_id}
doc_type: policy
version: "1.0"
effective_date: 2020-01-01
approval_status: approved
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


class TestParseArgs:
    def test_default_is_incremental_not_dry_run_not_full(self) -> None:
        args = _parse_args([])
        assert args.full is False
        assert args.incremental is False
        assert args.dry_run is False

    def test_full_flag(self) -> None:
        args = _parse_args(["--full"])
        assert args.full is True

    def test_dry_run_flag_combines_with_full(self) -> None:
        args = _parse_args(["--full", "--dry-run"])
        assert args.full is True
        assert args.dry_run is True

    def test_full_and_incremental_are_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            _parse_args(["--full", "--incremental"])


class TestRun:
    def test_default_run_embeds_new_documents(self, tmp_path: Path, embedder: Embedder) -> None:
        _write_doc(tmp_path, doc_id="DOC-A")
        client = QdrantClient(":memory:")

        summary = run(
            client,
            embedder,
            documents_dir=tmp_path,
            alias="cli_test",
            model_id=DENSE_MODEL,
            args=_parse_args([]),
        )

        assert summary.embedded_docs == ["DOC-A"]

    def test_full_flag_reembeds_even_an_unchanged_document(
        self, tmp_path: Path, embedder: Embedder
    ) -> None:
        _write_doc(tmp_path, doc_id="DOC-A")
        client = QdrantClient(":memory:")
        run(
            client,
            embedder,
            documents_dir=tmp_path,
            alias="cli_full_test",
            model_id=DENSE_MODEL,
            args=_parse_args([]),
        )

        second = run(
            client,
            embedder,
            documents_dir=tmp_path,
            alias="cli_full_test",
            model_id=DENSE_MODEL,
            args=_parse_args(["--full"]),
        )

        assert second.embedded_docs == ["DOC-A"]
        assert second.skipped_docs == []

    def test_dry_run_flag_does_not_write_to_qdrant(
        self, tmp_path: Path, embedder: Embedder
    ) -> None:
        _write_doc(tmp_path, doc_id="DOC-A")
        client = QdrantClient(":memory:")

        summary = run(
            client,
            embedder,
            documents_dir=tmp_path,
            alias="cli_dry_run_test",
            model_id=DENSE_MODEL,
            args=_parse_args(["--dry-run"]),
        )

        assert summary.embedded_docs == ["DOC-A"]
        assert client.collection_exists(summary.collection_name) is False
