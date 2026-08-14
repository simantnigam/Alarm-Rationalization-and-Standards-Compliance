"""compliance.ranking.rank: combines measured evidence into a score-ordered list, then
gates by verdict (01-architecture.md §7, 02-phases.md Phase 7) -- a candidate's rank
POSITION is driven purely by its nuisance_score; a failing verdict never moves it out of
that position, it only marks `overall_status`. That separation is what makes
test_sif_alarm_refused_despite_top_score meaningful: the SIF alarm ranks #1 on evidence
and is still refused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from copilot.compliance.engine import evaluate
from copilot.compliance.ranking import rank
from copilot.compliance.rules import load_rules
from copilot.domain.alarm import AlarmSeverity, SafetyClassification
from copilot.domain.candidate import CandidateCategory, RationalizationCandidate
from copilot.domain.verdict import Verdict, VerdictStatus

REAL_RULE_PACK_PATH = Path(__file__).parent.parent.parent / "rag" / "documents" / "rule_pack.yaml"


def _candidate(**overrides: Any) -> RationalizationCandidate:
    fields: dict[str, Any] = {
        "alarm_code": "BFP101-VIB-HH",
        "asset_id": "NP-U1-BFP-101",
        "asset_name": "Boiler Feed Pump 101",
        "site": "NorthPlant",
        "unit": "Unit 1",
        "severity": AlarmSeverity.HIGH,
        "is_sif_related": False,
        "safety_classification": SafetyClassification.NONE,
        "occurrences": 30,
        "occurrences_90d": 30,
        "occurrences_per_day": 0.5,
        "stale_occurrences": 0,
        "max_stale_minutes": 0.0,
        "chatter_index": 2,
        "fleeting_count": 0,
        "fleeting_rate": 0.0,
        "avg_ack_delay_s": 10.0,
        "max_ack_delay_s": 20.0,
        "unacknowledged_rate": 0.05,
        "nuisance_score": 70.0,
        "category": CandidateCategory.RECURRING,
        "reason": "test fixture",
    }
    fields.update(overrides)
    return RationalizationCandidate(**fields)


def _verdict(*, alarm_code: str, status: VerdictStatus, overriding: bool = False) -> Verdict:
    return Verdict(
        rule_id="TEST-001",
        alarm_code=alarm_code,
        doc_id="DOC-1",
        clause_id="1.1",
        status=status,
        measured=1,
        threshold=1,
        margin=None,
        message="test verdict",
        overriding=overriding,
    )


class TestScoreOrdering:
    def test_orders_purely_by_nuisance_score_descending(self) -> None:
        candidates = [
            _candidate(alarm_code="LOW", nuisance_score=40),
            _candidate(alarm_code="HIGH", nuisance_score=90),
            _candidate(alarm_code="MID", nuisance_score=65),
        ]
        ranked = rank(candidates, verdicts=[])
        assert [rc.candidate.alarm_code for rc in ranked] == ["HIGH", "MID", "LOW"]

    def test_a_failing_verdict_does_not_move_the_candidate_out_of_its_score_position(
        self,
    ) -> None:
        candidates = [
            _candidate(alarm_code="A", nuisance_score=90),
            _candidate(alarm_code="B", nuisance_score=50),
        ]
        verdicts = [_verdict(alarm_code="A", status=VerdictStatus.FAIL, overriding=True)]

        ranked = rank(candidates, verdicts)

        assert [rc.candidate.alarm_code for rc in ranked] == ["A", "B"]
        assert ranked[0].overall_status == VerdictStatus.FAIL
        assert ranked[1].overall_status == VerdictStatus.PASS


class TestOverallStatusAggregation:
    def test_no_verdicts_is_pass(self) -> None:
        ranked = rank([_candidate(alarm_code="A")], verdicts=[])
        assert ranked[0].overall_status == VerdictStatus.PASS

    def test_all_pass_verdicts_is_pass(self) -> None:
        verdicts = [_verdict(alarm_code="A", status=VerdictStatus.PASS)]
        ranked = rank([_candidate(alarm_code="A")], verdicts)
        assert ranked[0].overall_status == VerdictStatus.PASS

    def test_any_needs_review_without_a_fail_is_needs_review(self) -> None:
        verdicts = [
            _verdict(alarm_code="A", status=VerdictStatus.PASS),
            _verdict(alarm_code="A", status=VerdictStatus.NEEDS_REVIEW),
        ]
        ranked = rank([_candidate(alarm_code="A")], verdicts)
        assert ranked[0].overall_status == VerdictStatus.NEEDS_REVIEW

    def test_any_fail_wins_over_needs_review_and_pass(self) -> None:
        verdicts = [
            _verdict(alarm_code="A", status=VerdictStatus.PASS),
            _verdict(alarm_code="A", status=VerdictStatus.NEEDS_REVIEW),
            _verdict(alarm_code="A", status=VerdictStatus.FAIL),
        ]
        ranked = rank([_candidate(alarm_code="A")], verdicts)
        assert ranked[0].overall_status == VerdictStatus.FAIL

    def test_verdicts_for_a_different_alarm_code_are_not_attributed_to_this_candidate(
        self,
    ) -> None:
        verdicts = [_verdict(alarm_code="OTHER", status=VerdictStatus.FAIL)]
        ranked = rank([_candidate(alarm_code="A")], verdicts)
        assert ranked[0].verdicts == []
        assert ranked[0].overall_status == VerdictStatus.PASS


def test_sif_alarm_refused_despite_top_score() -> None:
    """The named Phase 7 exit-gate test: a high-nuisance, high-recurrence, SIF-linked
    alarm ranks #1 by measured evidence and is still returned FAIL, citing
    SAF-INST-005 §2.1 -- the overriding safety gate, not a weighted factor.
    """
    rules = load_rules(REAL_RULE_PACK_PATH)

    sif_candidate = _candidate(
        alarm_code="SIF-DEMO-001",
        site="NorthPlant",
        nuisance_score=95.0,
        occurrences_90d=80,
        unacknowledged_rate=0.05,
        is_sif_related=True,
        safety_classification=SafetyClassification.SIF,
    )
    ordinary_candidate = _candidate(
        alarm_code="ORDINARY-001", site="NorthPlant", nuisance_score=70.0, occurrences_90d=30
    )

    verdicts = evaluate(sif_candidate, rules) + evaluate(ordinary_candidate, rules)
    ranked = rank([sif_candidate, ordinary_candidate], verdicts)

    assert ranked[0].candidate.alarm_code == "SIF-DEMO-001"  # top-ranked on evidence
    assert ranked[0].overall_status == VerdictStatus.FAIL  # still refused

    safety_verdict = next(v for v in ranked[0].verdicts if v.rule_id == "SAF-001")
    assert safety_verdict.status == VerdictStatus.FAIL
    assert safety_verdict.overriding is True
    assert safety_verdict.clause_ref == "SAF-INST-005 §2.1"
