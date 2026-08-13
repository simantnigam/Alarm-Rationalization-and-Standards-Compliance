"""Session-scoped FastEmbed models -- loading dense + sparse ONNX models is not free,
so every RAG test in this session shares one Embedder instance.
"""

from __future__ import annotations

import pytest

from rag.ingestion.embedder import Embedder


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    return Embedder()
