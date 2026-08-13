"""CopilotState: the four-node walking-skeleton slice (02-phases.md Phase 2.5). Phase 8
extends this with scope/evidence/verdicts/degraded/evidence_gap/pending_approval."""

from __future__ import annotations

from typing import TypedDict

from copilot.domain.citation import Citation
from copilot.domain.trace import ToolInvocation
from copilot.planning.models import AnalysisPlan


class CopilotState(TypedDict):
    conversation_id: str
    trace_id: str
    question: str
    plan: AnalysisPlan | None
    invocations: list[ToolInvocation]
    citations: list[Citation]
    answer: str
