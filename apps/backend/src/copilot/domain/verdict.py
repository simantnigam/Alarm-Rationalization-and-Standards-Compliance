"""Verdict: the output of the deterministic compliance rule engine (Phase 7). Never
produced by the LLM -- see 00-decisions.md D-07.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

MeasuredValue = float | int | str | bool | None


class VerdictStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    doc_id: str
    clause_id: str
    status: VerdictStatus
    measured: MeasuredValue
    threshold: MeasuredValue
    margin: float | None
    message: str

    @property
    def clause_ref(self) -> str:
        return f"{self.doc_id} §{self.clause_id}"

    @model_validator(mode="after")
    def _check_message_present(self) -> Verdict:
        if not self.message.strip():
            raise ValueError(
                "message must be non-empty -- a verdict without an explanation is not auditable"
            )
        return self
