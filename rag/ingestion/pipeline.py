"""Single-document ingestion (`ingest_document`): load -> chunk -> embed -> upsert.
Walking-skeleton slice (02-phases.md Phase 2.5) -- one document, one collection, no
diffing; still used by the walking-skeleton tests that intentionally exercise just one
document. `run_ingestion` below is Phase 6's full incremental (sha256 diff) +
blue/green alias-swap pipeline (01-architecture.md §6, 07-rag-corpus.md §5, D-12) over
the whole rag/documents/ corpus.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from rag.ingestion.chunker import Chunk, chunk_by_clause
from rag.ingestion.collection import (
    ensure_collection,
    next_versioned_collection_name,
    resolve_alias,
    swap_alias,
)
from rag.ingestion.embedder import DENSE_MODEL, Embedder
from rag.ingestion.injection_scan import scan_for_injection
from rag.ingestion.loader import DocumentMetadata, LoadedDocument, extract, load_markdown

_INGEST_SUFFIXES = (".md", ".pdf")


def _point_id(doc_id: str, clause_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}#{clause_id}"))


def ingest_document(
    client: QdrantClient, embedder: Embedder, doc_path: Path, *, collection_name: str
) -> int:
    doc = load_markdown(doc_path)
    chunks = chunk_by_clause(doc.body)
    if not chunks:
        return 0

    texts = [chunk.text for chunk in chunks]
    dense_vectors = embedder.embed_dense(texts)
    sparse_vectors = embedder.embed_sparse(texts)

    points = [
        models.PointStruct(
            id=_point_id(doc.metadata.doc_id, chunk.clause_id),
            vector={"dense": dense, "bm25": sparse},
            payload={
                "doc_id": doc.metadata.doc_id,
                "title": doc.metadata.title,
                "doc_type": doc.metadata.doc_type,
                "version": doc.metadata.version,
                "effective_date": f"{doc.metadata.effective_date.isoformat()}T00:00:00Z",
                "approval_status": doc.metadata.approval_status,
                "site_scope": doc.metadata.site_scope,
                "unit_scope": doc.metadata.unit_scope,
                "section_path": chunk.section_path,
                "clause_id": chunk.clause_id,
                "clause_title": chunk.title,
                "text": chunk.text,
                "sha256": doc.sha256,
                "injection_flag": scan_for_injection(chunk.text),
            },
        )
        for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


def _is_indexable(metadata: DocumentMetadata, *, now: date) -> bool:
    """MoC gating (01-architecture.md §6; ALM-PHIL-001 §6): only an approved document
    whose effective_date has already passed is ever indexed."""
    return metadata.approval_status == "approved" and metadata.effective_date <= now


def corpus_paths(documents_dir: Path) -> list[Path]:
    """rag/documents/*.md and *.pdf only -- never _source/ or MANIFEST.md (provenance
    documentation, not a corpus document with front matter), so a PDF's markdown source
    and its rendered artifact can never both be ingested (07-rag-corpus.md §5)."""
    return sorted(
        p
        for p in documents_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _INGEST_SUFFIXES and p.name != "MANIFEST.md"
    )


def _payload(
    doc: LoadedDocument, chunk: Chunk, *, model_id: str, ingested_at: str
) -> dict[str, Any]:
    page = doc.clause_pages.get(chunk.clause_id) if doc.clause_pages else None
    return {
        "doc_id": doc.metadata.doc_id,
        "title": doc.metadata.title,
        "doc_type": doc.metadata.doc_type,
        "version": doc.metadata.version,
        "effective_date": f"{doc.metadata.effective_date.isoformat()}T00:00:00Z",
        "approval_status": doc.metadata.approval_status,
        "site_scope": doc.metadata.site_scope,
        "unit_scope": doc.metadata.unit_scope,
        "section_path": chunk.section_path,
        "clause_id": chunk.clause_id,
        "clause_title": chunk.title,
        "text": chunk.text,
        "page": page,
        "sha256": doc.sha256,
        "injection_flag": scan_for_injection(chunk.text),
        "model_id": model_id,
        "ingested_at": ingested_at,
    }


@dataclass(frozen=True)
class IngestSummary:
    collection_name: str
    embedded_docs: list[str] = field(default_factory=list)
    skipped_docs: list[str] = field(default_factory=list)
    gated_docs: list[str] = field(default_factory=list)
    purged_docs: list[str] = field(default_factory=list)
    total_chunks: int = 0
    quarantined_chunks: int = 0


def _existing_points_by_doc(
    client: QdrantClient, collection_name: str
) -> dict[str, list[models.PointStruct]]:
    by_doc: dict[str, list[models.PointStruct]] = {}
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection_name,
            with_payload=True,
            with_vectors=True,
            limit=256,
            offset=offset,
        )
        for record in records:
            assert record.payload is not None
            assert record.vector is not None  # with_vectors=True guarantees this
            by_doc.setdefault(record.payload["doc_id"], []).append(
                # The scrolled vector shape is always what this collection was built
                # with (named dense + sparse) -- narrower than PointStruct's stub, which
                # also allows Document/Image/InferenceObject inputs we never construct.
                models.PointStruct(
                    id=record.id,
                    vector=record.vector,  # type: ignore[arg-type]
                    payload=record.payload,
                )
            )
        if offset is None:
            break
    return by_doc


def _validate(
    client: QdrantClient,
    collection_name: str,
    *,
    expected_count: int,
    spot_check_id: int | str | uuid.UUID | None,
) -> None:
    actual = client.count(collection_name).count
    if actual != expected_count:
        raise RuntimeError(
            f"ingestion validation failed for {collection_name!r}: expected {expected_count} "
            f"points, found {actual}"
        )
    if spot_check_id is not None and not client.retrieve(collection_name, ids=[spot_check_id]):
        raise RuntimeError(
            f"ingestion validation failed for {collection_name!r}: spot-check point "
            f"{spot_check_id!r} not found"
        )


def run_ingestion(
    client: QdrantClient,
    embedder: Embedder,
    *,
    documents_dir: Path,
    alias: str = "policy_chunks",
    model_id: str = DENSE_MODEL,
    now: date | None = None,
    dry_run: bool = False,
    force_full: bool = False,
) -> IngestSummary:
    """manifest diff -> load -> chunk -> metadata -> injection scan -> embed (changed
    docs only) -> build NEW collection -> validate -> swap alias
    (01-architecture.md §6). Incremental (C-3, no separate manifest table): diffs
    against the sha256 values already in the alias-resolved LIVE collection's payloads;
    an unchanged document's points are copied forward instead of being re-embedded, so
    only new or changed documents pay the embedding cost. `force_full` (the CLI's
    `--full`) skips that reuse and re-embeds every indexable document regardless of
    whether its sha256 matches -- e.g. after a genuine embedding-model change. A
    `dry_run` computes the same summary without calling the embedder or touching Qdrant.
    """
    now = now or date.today()
    ingested_at = datetime.now(UTC).isoformat()

    old_collection = resolve_alias(client, alias)
    old_points_by_doc = (
        _existing_points_by_doc(client, old_collection) if old_collection is not None else {}
    )
    new_collection = next_versioned_collection_name(alias, model_id, old_collection)

    points_to_upsert: list[models.PointStruct] = []
    all_payloads: list[dict[str, Any]] = []
    embedded_docs: list[str] = []
    skipped_docs: list[str] = []
    gated_docs: list[str] = []
    seen_doc_ids: set[str] = set()

    for path in corpus_paths(documents_dir):
        doc = extract(path)
        doc_id = doc.metadata.doc_id
        seen_doc_ids.add(doc_id)

        if not _is_indexable(doc.metadata, now=now):
            gated_docs.append(doc_id)
            continue

        previous_points = old_points_by_doc.get(doc_id)
        if (
            not force_full
            and previous_points
            and previous_points[0].payload.get("sha256") == doc.sha256  # type: ignore[union-attr]
        ):
            points_to_upsert.extend(previous_points)
            all_payloads.extend(p.payload for p in previous_points)  # type: ignore[misc]
            skipped_docs.append(doc_id)
            continue

        chunks = chunk_by_clause(doc.body)
        payloads = [_payload(doc, c, model_id=model_id, ingested_at=ingested_at) for c in chunks]
        all_payloads.extend(payloads)
        embedded_docs.append(doc_id)

        if not dry_run and chunks:
            texts = [c.text for c in chunks]
            dense_vectors = embedder.embed_dense(texts)
            sparse_vectors = embedder.embed_sparse(texts)
            points_to_upsert.extend(
                models.PointStruct(
                    id=_point_id(doc_id, chunk.clause_id),
                    vector={"dense": dense, "bm25": sparse},
                    payload=payload,
                )
                for chunk, dense, sparse, payload in zip(
                    chunks, dense_vectors, sparse_vectors, payloads, strict=True
                )
            )

    purged_docs = sorted(set(old_points_by_doc) - seen_doc_ids)
    summary = IngestSummary(
        collection_name=new_collection,
        embedded_docs=embedded_docs,
        skipped_docs=skipped_docs,
        gated_docs=gated_docs,
        purged_docs=purged_docs,
        total_chunks=len(all_payloads),
        quarantined_chunks=sum(1 for p in all_payloads if p["injection_flag"]),
    )
    if dry_run:
        return summary

    ensure_collection(client, new_collection)
    if points_to_upsert:
        client.upsert(collection_name=new_collection, points=points_to_upsert)

    spot_check_id = points_to_upsert[0].id if points_to_upsert else None
    _validate(
        client, new_collection, expected_count=len(points_to_upsert), spot_check_id=spot_check_id
    )
    swap_alias(client, alias=alias, new_collection=new_collection)
    return summary
