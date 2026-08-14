"""The coupling guard 07-rag-corpus.md §4 calls for: every `predicate.metric` named in
rag/documents/rule_pack.yaml must be a field on RationalizationCandidate, or a rule
would silently evaluate against a metric the API never returns. Phase 7's rules.py
loader/validator formalizes this pack for the compliance engine; this test only proves
the pack and the candidate model haven't already drifted apart.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from copilot.domain.candidate import RationalizationCandidate

RULE_PACK_PATH = Path(__file__).parent.parent.parent / "rag" / "documents" / "rule_pack.yaml"


def _load_rules() -> list[dict]:
    with RULE_PACK_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]


def test_rule_pack_is_non_empty() -> None:
    assert len(_load_rules()) >= 1


def test_every_predicate_metric_exists_on_the_candidate_model() -> None:
    candidate_fields = set(RationalizationCandidate.model_fields)
    rules = _load_rules()

    missing = [
        (rule["rule_id"], rule["predicate"]["metric"])
        for rule in rules
        if rule["predicate"]["metric"] not in candidate_fields
    ]

    assert missing == []


def test_every_rule_carries_a_source_clause() -> None:
    for rule in _load_rules():
        assert "source" in rule
        assert rule["source"].get("doc_id")
        assert rule["source"].get("clause_id")


def test_the_overriding_safety_rule_is_flagged_as_such() -> None:
    rules = {rule["rule_id"]: rule for rule in _load_rules()}
    saf_001 = rules["SAF-001"]
    assert saf_001["severity"] == "safety"
    assert saf_001["overriding"] is True


def test_the_deliberate_site_conflict_is_present() -> None:
    rules = {rule["rule_id"]: rule for rule in _load_rules()}
    north = rules["SITE-NP-001"]
    east = rules["SITE-ER-001"]
    assert north["predicate"]["value"] == 25
    assert east["predicate"]["value"] == 40
    assert north["applies_to"]["site_scope"] == "NorthPlant"
    assert east["applies_to"]["site_scope"] == "EastRefinery"
