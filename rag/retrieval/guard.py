"""Startup guard (01-architecture.md §6, R-07): copilot-api refuses to boot unless the
alias resolves, the collection is non-empty, and its stamped `model_id` matches
`EMBED_MODEL`. An embedding model-id mismatch never resolves by waiting -- it's a
configuration error, not dependency unavailability -- so this fails fast rather than
retrying, the same rule 02-phases.md Phase 5 draws for MCP discovery (R-04 vs R-07).
"""

from __future__ import annotations

from qdrant_client import QdrantClient

from rag.ingestion.collection import resolve_alias


class RagGuardError(Exception):
    """Raised when the RAG collection isn't in a servable state."""


def assert_rag_collection_ready(
    client: QdrantClient, *, alias: str, expected_model_id: str
) -> None:
    collection_name = resolve_alias(client, alias)
    if collection_name is None:
        raise RagGuardError(f"alias {alias!r} does not resolve -- has rag-ingest ever run?")

    if client.count(collection_name).count == 0:
        raise RagGuardError(f"collection {collection_name!r} (alias {alias!r}) is empty")

    records, _ = client.scroll(collection_name, with_payload=["model_id"], limit=1)
    stamped_model_id = (
        records[0].payload.get("model_id") if records and records[0].payload else None
    )
    if stamped_model_id != expected_model_id:
        raise RagGuardError(
            f"collection {collection_name!r} was embedded with model_id={stamped_model_id!r}, "
            f"but EMBED_MODEL={expected_model_id!r} -- re-run rag-ingest --full"
        )
