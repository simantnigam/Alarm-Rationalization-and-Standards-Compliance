"""LLMPort: no sampling knobs exposed (D-06) -- depth is an abstract Effort enum in
Phase 8, adapters translate or drop it per the provider capability matrix. Walking
skeleton (Phase 2.5) only needs `generate`; Phase 8 adds `structured`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMPort(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...
