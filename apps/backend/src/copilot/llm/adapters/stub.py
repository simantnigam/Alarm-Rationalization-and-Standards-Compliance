"""Deterministic stub provider: what CI and the offline demo path run against, with no
API keys and zero cost (D-01, D-06b). Echoes its input predictably rather than
generating free text, so tests can assert on the output.
"""

from __future__ import annotations

from copilot.llm.port import LLMPort


class StubLLMAdapter(LLMPort):
    async def generate(self, prompt: str) -> str:
        return f"[stub-answer] {prompt}"
