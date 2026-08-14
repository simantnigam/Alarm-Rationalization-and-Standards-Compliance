"""Session-scoped FastEmbed models -- loading dense + sparse ONNX models is not free,
so every RAG test in this session shares one Embedder instance.
"""

from __future__ import annotations

import pytest
from fastembed.rerank.cross_encoder import TextCrossEncoder

from rag.ingestion.embedder import Embedder
from rag.retrieval.service import DEFAULT_RERANK_MODEL


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="session")
def reranker() -> TextCrossEncoder:
    return TextCrossEncoder(DEFAULT_RERANK_MODEL)
