"""CopilotResponse: the structured, typed final answer returned by POST /api/chat
(5.1.f). Measured evidence, policy requirements, and generated narrative stay in
separate fields all the way to the GUI -- see 00-decisions.md D-07.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from copilot.domain.candidate import RationalizationCandidate
from copilot.domain.citation import Citation
from copilot.domain.trace import ExecutionTrace
from copilot.domain.verdict import Verdict


class CopilotResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    question: str
    answer: str

    candidates: list[RationalizationCandidate]
    verdicts: list[Verdict]
    citations: list[Citation]
    trace: ExecutionTrace

    degraded: bool
    evidence_gap: bool
    pending_approval: dict[str, Any] | None = None
    clarification: str | None = None
