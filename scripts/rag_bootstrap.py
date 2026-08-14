"""rag-ingest CLI (01-architecture.md §6, 07-rag-corpus.md §5): the real lifecycle
owner for the RAG index, run via `docker compose --profile batch run --rm rag-ingest`
(the same command also backs the `rag-bootstrap` one-shot service in
docker-compose.yml -- `make ingest` is the Linux/Mac shortcut). Walking-skeleton slice
(02-phases.md Phase 2.5) ingested one document with no diffing; Phase 6 replaces that
with the full incremental (sha256 diff) + blue/green alias-swap pipeline (D-12),
reporting embedded / skipped / gated / purged / quarantined counts.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from qdrant_client import QdrantClient

from rag.ingestion.embedder import DENSE_MODEL, Embedder
from rag.ingestion.pipeline import IngestSummary, run_ingestion


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest rag/documents/ into Qdrant.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--full",
        action="store_true",
        help="Re-embed every document, ignoring the sha256 diff (e.g. after an EMBED_MODEL change)",
    )
    mode.add_argument(
        "--incremental",
        action="store_true",
        help="Embed only new or changed documents (default behaviour).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen without calling the embedder or writing to Qdrant.",
    )
    return parser.parse_args(argv)


def _print_summary(summary: IngestSummary) -> None:
    print(f"collection: {summary.collection_name}")
    print(f"embedded    ({len(summary.embedded_docs)}): {', '.join(summary.embedded_docs) or '-'}")
    print(f"skipped     ({len(summary.skipped_docs)}): {', '.join(summary.skipped_docs) or '-'}")
    print(f"gated (MoC) ({len(summary.gated_docs)}): {', '.join(summary.gated_docs) or '-'}")
    print(f"purged      ({len(summary.purged_docs)}): {', '.join(summary.purged_docs) or '-'}")
    print(f"total chunks: {summary.total_chunks}")
    print(f"quarantined chunks (injection-flagged): {summary.quarantined_chunks}")


def run(
    client: QdrantClient,
    embedder: Embedder,
    *,
    documents_dir: Path,
    alias: str,
    model_id: str,
    args: argparse.Namespace,
) -> IngestSummary:
    summary = run_ingestion(
        client,
        embedder,
        documents_dir=documents_dir,
        alias=alias,
        model_id=model_id,
        dry_run=args.dry_run,
        force_full=args.full,
    )
    _print_summary(summary)
    return summary


def main(argv: list[str] | None = None) -> None:  # pragma: no cover -- process entrypoint
    args = _parse_args(argv)

    documents_dir = Path(os.environ.get("DOCUMENT_PATH", "./rag/documents"))
    alias = os.environ.get("QDRANT_COLLECTION_ALIAS", "policy_chunks")
    vector_store_url = os.environ["VECTOR_STORE_URL"]
    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")
    model_id = os.environ.get("EMBED_MODEL", DENSE_MODEL)

    client = QdrantClient(url=vector_store_url)
    embedder = Embedder(dense_model=model_id, cache_dir=cache_dir)
    run(client, embedder, documents_dir=documents_dir, alias=alias, model_id=model_id, args=args)


if __name__ == "__main__":  # pragma: no cover
    main()
