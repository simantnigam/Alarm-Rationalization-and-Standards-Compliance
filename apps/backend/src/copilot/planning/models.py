"""AnalysisPlan: the typed, LLM-produced (or hardcoded, for the walking skeleton)
artifact the executor runs -- testable and replayable without a model (D-01)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PlanStep(BaseModel):
    tool_name: str
    arguments: dict[str, Any]


class AnalysisPlan(BaseModel):
    steps: list[PlanStep]
