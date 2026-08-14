"""Combines measured evidence into a score-ordered list, then gates by verdict
(01-architecture.md §7, 02-phases.md Phase 7). Rank POSITION is driven purely by
`nuisance_score` -- the composite frequency/chattering/fleeting/unacknowledged-rate
metric ALM-CRIT-003 §3.2 already gates eligibility on -- never by verdict status; a
failing verdict changes `overall_status`, never where a candidate sorts. That
separation is what "gates, not weighted factors" means in practice: a candidate can
rank #1 on evidence and still be refused.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from copilot.domain.candidate import RationalizationCandidate
from copilot.domain.verdict import Verdict, VerdictStatus


class RankedCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate: RationalizationCandidate
    verdicts: list[Verdict]
    overall_status: VerdictStatus


def rank(
    candidates: list[RationalizationCandidate], verdicts: list[Verdict]
) -> list[RankedCandidate]:
    verdicts_by_code: dict[str, list[Verdict]] = defaultdict(list)
    for verdict in verdicts:
        verdicts_by_code[verdict.alarm_code].append(verdict)

    ranked = [
        RankedCandidate(
            candidate=candidate,
            verdicts=verdicts_by_code[candidate.alarm_code],
            overall_status=_overall_status(verdicts_by_code[candidate.alarm_code]),
        )
        for candidate in candidates
    ]
    ranked.sort(key=lambda rc: rc.candidate.nuisance_score, reverse=True)
    return ranked


def _overall_status(verdicts: list[Verdict]) -> VerdictStatus:
    if any(v.status == VerdictStatus.FAIL for v in verdicts):
        return VerdictStatus.FAIL
    if any(v.status == VerdictStatus.NEEDS_REVIEW for v in verdicts):
        return VerdictStatus.NEEDS_REVIEW
    return VerdictStatus.PASS
