"""FastEmbed dense + sparse embeddings -- no embedding API calls (D-04). Loading the
ONNX models is not free; callers should hold one Embedder for the process lifetime.
"""

from __future__ import annotations

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import models

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
DENSE_DIM = 384


class Embedder:
    def __init__(
        self,
        *,
        dense_model: str = DENSE_MODEL,
        sparse_model: str = SPARSE_MODEL,
        cache_dir: str | None = None,
    ) -> None:
        self._dense = TextEmbedding(dense_model, cache_dir=cache_dir)
        self._sparse = SparseTextEmbedding(sparse_model, cache_dir=cache_dir)

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._dense.embed(texts)]

    def embed_sparse(self, texts: list[str]) -> list[models.SparseVector]:
        return [
            models.SparseVector(indices=vector.indices.tolist(), values=vector.values.tolist())
            for vector in self._sparse.embed(texts)
        ]
