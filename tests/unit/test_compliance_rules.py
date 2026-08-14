"""compliance.rules.load_rules: loader/validator for rule_pack.yaml (02-phases.md
Phase 7). Parses the real committed pack (already coupling-tested against
RationalizationCandidate in test_rule_pack_metrics_exist.py) into typed Rule objects,
and rejects a pack that's structurally malformed in ways the raw YAML wouldn't catch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from copilot.compliance.rules import Rule, load_rules
from copilot.domain.verdict import VerdictStatus

REAL_RULE_PACK_PATH = Path(__file__).parent.parent.parent / "rag" / "documents" / "rule_pack.yaml"


def _write_pack(tmp_path: Path, rules: list[dict[str, Any]]) -> Path:
    path = tmp_path / "rule_pack.yaml"
    path.write_text(yaml.safe_dump({"rules": rules}), encoding="utf-8")
    return path


def _base_rule(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "rule_id": "TEST-001",
        "kind": "eligibility",
        "source": {"doc_id": "DOC-1", "clause_id": "1.1"},
        "applies_to": {"site_scope": "ALL"},
        "predicate": {"metric": "occurrences_90d", "op": ">=", "value": 25},
        "outcome_when_false": "FAIL",
        "message": "test message",
    }
    rule.update(overrides)
    return rule


class TestLoadsTheRealRulePack:
    def test_loads_all_ten_rules(self) -> None:
        rules = load_rules(REAL_RULE_PACK_PATH)
        assert len(rules) == 10
        assert all(isinstance(r, Rule) for r in rules)

    def test_saf_001_is_overriding_with_safety_severity(self) -> None:
        rules = {r.rule_id: r for r in load_rules(REAL_RULE_PACK_PATH)}
        saf_001 = rules["SAF-001"]
        assert saf_001.overriding is True
        assert saf_001.severity == "safety"
        assert saf_001.source.doc_id == "SAF-INST-005"
        assert saf_001.source.clause_id == "2.1"
        assert saf_001.outcome_when_true == VerdictStatus.FAIL

    def test_site_specific_rules_carry_their_site_scope(self) -> None:
        rules = {r.rule_id: r for r in load_rules(REAL_RULE_PACK_PATH)}
        assert rules["SITE-NP-001"].applies_to.site_scope == "NorthPlant"
        assert rules["SITE-ER-001"].applies_to.site_scope == "EastRefinery"

    def test_no_other_rule_is_overriding(self) -> None:
        rules = load_rules(REAL_RULE_PACK_PATH)
        overriding = [r.rule_id for r in rules if r.overriding]
        assert overriding == ["SAF-001"]


class TestValidation:
    def test_rejects_a_rule_with_neither_outcome_set(self, tmp_path: Path) -> None:
        path = _write_pack(tmp_path, [_base_rule(outcome_when_false=None, outcome_when_true=None)])
        with pytest.raises(ValueError, match="exactly one"):
            load_rules(path)

    def test_rejects_a_rule_with_both_outcomes_set(self, tmp_path: Path) -> None:
        path = _write_pack(tmp_path, [_base_rule(outcome_when_true="FAIL")])
        with pytest.raises(ValueError, match="exactly one"):
            load_rules(path)

    def test_rejects_overriding_true_without_safety_severity(self, tmp_path: Path) -> None:
        path = _write_pack(tmp_path, [_base_rule(overriding=True, severity=None)])
        with pytest.raises(ValueError, match="overriding"):
            load_rules(path)

    def test_rejects_an_unknown_predicate_operator(self, tmp_path: Path) -> None:
        path = _write_pack(
            tmp_path, [_base_rule(predicate={"metric": "x", "op": "~=", "value": 1})]
        )
        with pytest.raises(ValueError):
            load_rules(path)

    def test_rejects_duplicate_rule_ids(self, tmp_path: Path) -> None:
        path = _write_pack(tmp_path, [_base_rule(), _base_rule()])
        with pytest.raises(ValueError, match="duplicate"):
            load_rules(path)

    def test_rejects_an_unknown_kind(self, tmp_path: Path) -> None:
        path = _write_pack(tmp_path, [_base_rule(kind="not_a_real_kind")])
        with pytest.raises(ValueError):
            load_rules(path)
