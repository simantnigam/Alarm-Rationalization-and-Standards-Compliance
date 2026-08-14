"""Qdrant collection lifecycle: named dense + sparse vectors per collection (probed
pattern, R-01 closed against qdrant-client 1.19.0), plus blue/green alias management
(07-rag-corpus.md §5, 01-architecture.md §6 D-12): build a new versioned collection,
validate it, then atomically move the alias -- a query mid-rebuild still hits the old
collection, and rollback is just moving the alias back (old collections are never
auto-deleted, so that stays possible).
"""

from __future__ import annotations

import re

from qdrant_client import QdrantClient, models

from rag.ingestion.embedder import DENSE_DIM

_PAYLOAD_INDEXES: tuple[tuple[str, models.PayloadSchemaType], ...] = (
    ("doc_id", models.PayloadSchemaType.KEYWORD),
    ("doc_type", models.PayloadSchemaType.KEYWORD),
    ("site_scope", models.PayloadSchemaType.KEYWORD),
    ("clause_id", models.PayloadSchemaType.KEYWORD),
    ("injection_flag", models.PayloadSchemaType.BOOL),
    ("effective_date", models.PayloadSchemaType.DATETIME),
)


def ensure_collection(client: QdrantClient, name: str) -> None:
    if client.collection_exists(name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": models.VectorParams(size=DENSE_DIM, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={"bm25": models.SparseVectorParams()},
    )
    for field_name, schema in _PAYLOAD_INDEXES:
        client.create_payload_index(
            collection_name=name, field_name=field_name, field_schema=schema
        )


def resolve_alias(client: QdrantClient, alias: str) -> str | None:
    """The collection `alias` currently points at, or None if it doesn't resolve yet
    (first-ever ingestion run)."""
    for description in client.get_aliases().aliases:
        if description.alias_name == alias:
            return description.collection_name
    return None


_VERSION_RE = re.compile(r"__v(\d+)$")


def next_versioned_collection_name(
    alias: str, model_id: str, previous_collection: str | None
) -> str:
    """`{alias}__{model}__v{n}` (07-rag-corpus.md §5). `model_id` is slug-safe'd since
    HuggingFace model ids contain `/`, which Qdrant collection names reject.
    """
    model_slug = model_id.replace("/", "-")
    previous_version = 0
    if previous_collection is not None:
        match = _VERSION_RE.search(previous_collection)
        if match:
            previous_version = int(match.group(1))
    return f"{alias}__{model_slug}__v{previous_version + 1}"


def swap_alias(client: QdrantClient, *, alias: str, new_collection: str) -> None:
    """Atomically move `alias` to `new_collection`. A single
    `update_collection_aliases` call with both operations is processed as one request,
    so a concurrent query never observes the alias resolving to nothing.
    """
    operations: list[
        models.CreateAliasOperation | models.DeleteAliasOperation | models.RenameAliasOperation
    ] = [models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias))]
    operations.append(
        models.CreateAliasOperation(
            create_alias=models.CreateAlias(collection_name=new_collection, alias_name=alias)
        )
    )
    client.update_collection_aliases(change_aliases_operations=operations)
