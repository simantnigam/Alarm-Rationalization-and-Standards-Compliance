"""One-shot RAG bootstrap for a clean `docker compose up` (assumption A-11). Ingests
every document in DOCUMENT_PATH into the collection named by QDRANT_COLLECTION_ALIAS.
Walking-skeleton slice (02-phases.md Phase 2.5) -- Phase 6 replaces this with the full
incremental (sha256 diff) + blue/green alias-swap pipeline (D-12); this script is what
`rag-bootstrap` in docker-compose.yml runs today.
"""

from __future__ import annotations

import os
from pathlib import Path

from qdrant_client import QdrantClient

from rag.ingestion.collection import ensure_collection
from rag.ingestion.embedder import Embedder
from rag.ingestion.pipeline import ingest_document


def main() -> None:  # pragma: no cover -- process entrypoint, exercised via docker-compose
    documents_dir = Path(os.environ.get("DOCUMENT_PATH", "./rag/documents"))
    collection_name = os.environ.get("QDRANT_COLLECTION_ALIAS", "policy_chunks")
    vector_store_url = os.environ["VECTOR_STORE_URL"]
    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")

    client = QdrantClient(url=vector_store_url)
    embedder = Embedder(cache_dir=cache_dir)
    ensure_collection(client, collection_name)

    total = 0
    for doc_path in sorted(documents_dir.glob("*.md")):
        count = ingest_document(client, embedder, doc_path, collection_name=collection_name)
        print(f"ingested {doc_path.name}: {count} chunks")
        total += count
    print(f"RAG bootstrap complete: {total} chunks across the corpus")


if __name__ == "__main__":  # pragma: no cover
    main()
