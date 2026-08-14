"""compliance.engine.evaluate: the deterministic rule engine (02-phases.md Phase 7).
Pure -- no I/O, no LLM. Uses small synthetic rule sets so each behavior (PASS/FAIL/
NEEDS_REVIEW per rule kind, site-scope applicability, missing-metric handling, verdict
multiplicity) is exercised in isolation; test_compliance_ranking.py exercises the real
rule_pack.yaml end to end.
"""

from __future__ import annotations

from typing import Any

import pytest

from copilot.compliance.engine import evaluate
from copilot.compliance.rules import Rule, RuleApplicability, RulePredicate, RuleSource
from copilot.domain.alarm import AlarmSeverity, SafetyClassification
from copilot.domain.candidate import CandidateCategory, RationalizationCandidate
from copilot.domain.verdict import VerdictStatus


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


def _rule(**overrides: Any) -> Rule:
    fields: dict[str, Any] = {
        "rule_id": "TEST-001",
        "kind": "eligibility",
        "source": RuleSource(doc_id="DOC-1", clause_id="1.1"),
        "applies_to": RuleApplicability(site_scope="ALL"),
        "predicate": RulePredicate(metric="occurrences_90d", op=">=", value=25),
        "outcome_when_false": "FAIL",
        "message": "needs 25+ occurrences",
    }
    fields.update(overrides)
    return Rule(**fields)


class TestEligibilityRules:
    def test_predicate_true_with_outcome_when_false_yields_pass(self) -> None:
        rule = _rule()
        candidate = _candidate(occurrences_90d=30)
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.PASS

    def test_predicate_false_with_outcome_when_false_yields_the_configured_outcome(
        self,
    ) -> None:
        rule = _rule()
        candidate = _candidate(occurrences_90d=10)
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.FAIL


class TestProhibitionRules:
    def test_predicate_true_with_outcome_when_true_yields_the_configured_outcome(
        self,
    ) -> None:
        rule = _rule(
            kind="prohibition",
            predicate=RulePredicate(metric="severity", op="==", value="critical"),
            outcome_when_false=None,
            outcome_when_true="FAIL",
        )
        candidate = _candidate(severity=AlarmSeverity.CRITICAL)
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.FAIL

    def test_predicate_false_with_outcome_when_true_yields_pass(self) -> None:
        rule = _rule(
            kind="prohibition",
            predicate=RulePredicate(metric="severity", op="==", value="critical"),
            outcome_when_false=None,
            outcome_when_true="FAIL",
        )
        candidate = _candidate(severity=AlarmSeverity.HIGH)
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.PASS


class TestTriggerRules:
    def test_predicate_true_yields_needs_review(self) -> None:
        rule = _rule(
            kind="trigger",
            predicate=RulePredicate(metric="chatter_index", op=">=", value=6),
            outcome_when_false=None,
            outcome_when_true="NEEDS_REVIEW",
        )
        candidate = _candidate(chatter_index=8)
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.NEEDS_REVIEW

    def test_predicate_false_yields_pass(self) -> None:
        rule = _rule(
            kind="trigger",
            predicate=RulePredicate(metric="chatter_index", op=">=", value=6),
            outcome_when_false=None,
            outcome_when_true="NEEDS_REVIEW",
        )
        candidate = _candidate(chatter_index=1)
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.PASS


class TestVerdictShape:
    def test_verdict_carries_rule_and_source_and_measured_values(self) -> None:
        rule = _rule()
        candidate = _candidate(alarm_code="XYZ-001", occurrences_90d=10)
        verdict = evaluate(candidate, [rule])[0]

        assert verdict.rule_id == "TEST-001"
        assert verdict.alarm_code == "XYZ-001"
        assert verdict.doc_id == "DOC-1"
        assert verdict.clause_id == "1.1"
        assert verdict.measured == 10
        assert verdict.threshold == 25
        assert verdict.message == "needs 25+ occurrences"

    def test_margin_is_positive_when_comfortably_passing_a_gte_threshold(self) -> None:
        rule = _rule()
        candidate = _candidate(occurrences_90d=40)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.margin == 15

    def test_margin_is_negative_when_failing_a_gte_threshold(self) -> None:
        rule = _rule()
        candidate = _candidate(occurrences_90d=10)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.margin == -15

    def test_margin_is_positive_when_comfortably_under_an_lte_ceiling(self) -> None:
        rule = _rule(
            predicate=RulePredicate(metric="fleeting_rate", op="<=", value=0.2),
            outcome_when_false="FAIL",
        )
        candidate = _candidate(fleeting_rate=0.05)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.margin == pytest.approx(0.15)

    def test_margin_is_negative_when_exceeding_an_lte_ceiling(self) -> None:
        rule = _rule(
            predicate=RulePredicate(metric="fleeting_rate", op="<=", value=0.2),
            outcome_when_false="FAIL",
        )
        candidate = _candidate(fleeting_rate=0.5)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.margin == pytest.approx(-0.3)

    def test_margin_is_none_for_a_string_equality_predicate(self) -> None:
        rule = _rule(
            predicate=RulePredicate(metric="severity", op="==", value="critical"),
            outcome_when_false=None,
            outcome_when_true="FAIL",
        )
        candidate = _candidate(severity=AlarmSeverity.CRITICAL)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.margin is None

    def test_margin_is_none_for_a_numeric_equality_predicate(self) -> None:
        rule = _rule(
            predicate=RulePredicate(metric="chatter_index", op="==", value=5),
            outcome_when_false=None,
            outcome_when_true="NEEDS_REVIEW",
        )
        candidate = _candidate(chatter_index=5)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.margin is None

    def test_overriding_and_severity_are_denormalized_onto_the_verdict(self) -> None:
        rule = _rule(
            kind="prohibition",
            severity="safety",
            overriding=True,
            predicate=RulePredicate(metric="is_sif_related", op="==", value=True),
            outcome_when_false=None,
            outcome_when_true="FAIL",
        )
        candidate = _candidate(is_sif_related=True, safety_classification=SafetyClassification.SIF)
        verdict = evaluate(candidate, [rule])[0]
        assert verdict.overriding is True


class TestApplicability:
    def test_a_site_scoped_rule_does_not_fire_for_a_different_site(self) -> None:
        rule = _rule(applies_to=RuleApplicability(site_scope="EastRefinery"))
        candidate = _candidate(site="NorthPlant", occurrences_90d=10)
        verdicts = evaluate(candidate, [rule])
        assert verdicts == []

    def test_a_site_scoped_rule_fires_for_its_own_site(self) -> None:
        rule = _rule(applies_to=RuleApplicability(site_scope="EastRefinery"))
        candidate = _candidate(site="EastRefinery", occurrences_90d=10)
        verdicts = evaluate(candidate, [rule])
        assert len(verdicts) == 1

    def test_an_all_scoped_rule_fires_for_every_site(self) -> None:
        rule = _rule(applies_to=RuleApplicability(site_scope="ALL"))
        for site in ("NorthPlant", "EastRefinery", "SouthPlant"):
            candidate = _candidate(site=site, occurrences_90d=10)
            assert len(evaluate(candidate, [rule])) == 1

    def test_overlapping_all_and_site_scoped_rules_both_fire_with_distinct_clause_refs(
        self,
    ) -> None:
        corporate = _rule(
            rule_id="CORP-001",
            source=RuleSource(doc_id="ALM-CRIT-003", clause_id="3.1"),
            applies_to=RuleApplicability(site_scope="ALL"),
        )
        site_specific = _rule(
            rule_id="SITE-NP-001",
            source=RuleSource(doc_id="SITE-POL-007", clause_id="3.2"),
            applies_to=RuleApplicability(site_scope="NorthPlant"),
        )
        candidate = _candidate(site="NorthPlant", occurrences_90d=30)

        verdicts = evaluate(candidate, [corporate, site_specific])

        assert len(verdicts) == 2
        clause_refs = {v.clause_ref for v in verdicts}
        assert clause_refs == {"ALM-CRIT-003 §3.1", "SITE-POL-007 §3.2"}
        # Neither rule silently wins -- both verdicts are independently PASS here.
        assert all(v.status == VerdictStatus.PASS for v in verdicts)


class TestMissingMetric:
    def test_a_metric_not_on_the_candidate_or_in_evidence_yields_needs_review_not_a_crash(
        self,
    ) -> None:
        rule = _rule(predicate=RulePredicate(metric="does_not_exist", op=">=", value=1))
        candidate = _candidate()
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status == VerdictStatus.NEEDS_REVIEW
        assert verdicts[0].measured is None

    def test_a_metric_missing_from_the_candidate_but_present_in_evidence_is_used(
        self,
    ) -> None:
        rule = _rule(predicate=RulePredicate(metric="external_metric", op=">=", value=25))
        candidate = _candidate()
        verdicts = evaluate(candidate, [rule], evidence={"external_metric": 30})
        assert verdicts[0].status == VerdictStatus.PASS
        assert verdicts[0].measured == 30

    def test_never_silently_passes_a_missing_metric(self) -> None:
        rule = _rule(
            predicate=RulePredicate(metric="does_not_exist", op=">=", value=1),
            outcome_when_false="FAIL",
        )
        candidate = _candidate()
        verdicts = evaluate(candidate, [rule])
        assert verdicts[0].status != VerdictStatus.PASS
        assert verdicts[0].status == VerdictStatus.NEEDS_REVIEW


class TestMultipleRules:
    def test_evaluates_every_applicable_rule_independently_no_short_circuit(self) -> None:
        rules = [
            _rule(
                rule_id="A", predicate=RulePredicate(metric="occurrences_90d", op=">=", value=25)
            ),
            _rule(rule_id="B", predicate=RulePredicate(metric="nuisance_score", op=">=", value=60)),
            _rule(
                rule_id="C",
                kind="prohibition",
                predicate=RulePredicate(metric="is_sif_related", op="==", value=True),
                outcome_when_false=None,
                outcome_when_true="FAIL",
            ),
        ]
        candidate = _candidate(
            occurrences_90d=30,
            nuisance_score=70,
            is_sif_related=True,
            safety_classification=SafetyClassification.SIF,
        )
        verdicts = evaluate(candidate, rules)
        assert len(verdicts) == 3
        assert {v.rule_id for v in verdicts} == {"A", "B", "C"}
