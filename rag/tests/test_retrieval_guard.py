"""assert_rag_collection_ready (01-architecture.md §6, R-07): copilot-api's startup
guard. A model_id mismatch is a configuration error that must fail fast, not a
dependency-unavailability one that would retry (contrast 02-phases.md Phase 5's MCP
discovery backoff, R-04).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from rag.ingestion.collection import ensure_collection
from rag.ingestion.embedder import DENSE_MODEL, Embedder
from rag.ingestion.pipeline import run_ingestion
from rag.retrieval.guard import RagGuardError, assert_rag_collection_ready

DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"


def test_raises_when_the_alias_does_not_resolve() -> None:
    client = QdrantClient(":memory:")
    with pytest.raises(RagGuardError, match="does not resolve"):
        assert_rag_collection_ready(client, alias="never_ingested", expected_model_id=DENSE_MODEL)


def test_raises_when_the_collection_is_empty() -> None:
    client = QdrantClient(":memory:")
    ensure_collection(client, "empty_v1")
    from qdrant_client import models

    client.update_collection_aliases(
        change_aliases_operations=[
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name="empty_v1", alias_name="empty_alias"
                )
            )
        ]
    )
    with pytest.raises(RagGuardError, match="is empty"):
        assert_rag_collection_ready(client, alias="empty_alias", expected_model_id=DENSE_MODEL)


def test_raises_when_the_stamped_model_id_does_not_match(embedder: Embedder) -> None:
    client = QdrantClient(":memory:")
    run_ingestion(client, embedder, documents_dir=DOCUMENTS_DIR, alias="mismatch_test")

    with pytest.raises(RagGuardError, match="model_id"):
        assert_rag_collection_ready(
            client, alias="mismatch_test", expected_model_id="some-other-model"
        )


def test_passes_when_alias_resolves_collection_is_non_empty_and_model_id_matches(
    embedder: Embedder,
) -> None:
    client = QdrantClient(":memory:")
    run_ingestion(
        client, embedder, documents_dir=DOCUMENTS_DIR, alias="ready_test", model_id=DENSE_MODEL
    )

    assert_rag_collection_ready(client, alias="ready_test", expected_model_id=DENSE_MODEL)
