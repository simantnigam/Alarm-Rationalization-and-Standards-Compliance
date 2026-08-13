"""RationalizationCandidate: the per-alarm_code evidence payload the compliance engine
(Phase 7) evaluates against rule_pack.yaml. Every field here that a rule predicate can
name must exist on this model -- see 07-rag-corpus.md §4 on the coupling test.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from copilot.domain.alarm import AlarmSeverity, SafetyClassification


class CandidateCategory(StrEnum):
    STALE = "stale"
    RECURRING = "recurring"
    NUISANCE = "nuisance"
    CHATTERING = "chattering"
    FLEETING = "fleeting"


class RationalizationCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    alarm_code: str
    asset_id: str
    asset_name: str
    site: str
    unit: str
    severity: AlarmSeverity
    is_sif_related: bool
    safety_classification: SafetyClassification

    occurrences: int = Field(ge=0)
    occurrences_90d: int = Field(ge=0)
    occurrences_per_day: float = Field(ge=0)
    stale_occurrences: int = Field(ge=0)
    max_stale_minutes: float = Field(ge=0)
    chatter_index: int = Field(ge=0)
    fleeting_count: int = Field(ge=0)
    fleeting_rate: float = Field(ge=0, le=1)
    avg_ack_delay_s: float = Field(ge=0)
    max_ack_delay_s: float = Field(ge=0)
    unacknowledged_rate: float = Field(ge=0, le=1)
    nuisance_score: float = Field(ge=0, le=100)

    category: CandidateCategory
    reason: str
