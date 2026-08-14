"""Loader/validator for rule_pack.yaml (07-rag-corpus.md §4, 02-phases.md Phase 7).
Parses each rule into a typed Rule so engine.py never touches raw YAML, and rejects a
pack that's structurally broken in ways YAML parsing alone wouldn't catch -- a rule
with neither or both outcomes set, an `overriding` rule that isn't actually a safety
rule, or a duplicate rule_id.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from copilot.domain.verdict import MeasuredValue, VerdictStatus


class RuleKind(StrEnum):
    PROHIBITION = "prohibition"
    ELIGIBILITY = "eligibility"
    TRIGGER = "trigger"


class RuleSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    clause_id: str


class RuleApplicability(BaseModel):
    model_config = ConfigDict(frozen=True)

    site_scope: str = "ALL"


PredicateOp = Literal["==", "!=", ">=", "<=", ">", "<"]


class RulePredicate(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    op: PredicateOp
    value: MeasuredValue


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    kind: RuleKind
    severity: str | None = None
    overriding: bool = False
    source: RuleSource
    applies_to: RuleApplicability
    predicate: RulePredicate
    outcome_when_true: VerdictStatus | None = None
    outcome_when_false: VerdictStatus | None = None
    message: str

    @model_validator(mode="after")
    def _check_exactly_one_outcome(self) -> Rule:
        has_true = self.outcome_when_true is not None
        has_false = self.outcome_when_false is not None
        if has_true == has_false:
            raise ValueError(
                f"rule {self.rule_id!r} must set exactly one of "
                "outcome_when_true/outcome_when_false"
            )
        return self

    @model_validator(mode="after")
    def _check_overriding_requires_safety_severity(self) -> Rule:
        if self.overriding and self.severity != "safety":
            raise ValueError(
                f"rule {self.rule_id!r} sets overriding=true but severity != 'safety' "
                "(07-rag-corpus.md §4: overriding gates are safety rules, not weighted factors)"
            )
        return self


def load_rules(path: Path) -> list[Rule]:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    rules = [Rule.model_validate(entry) for entry in raw["rules"]]

    seen: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen:
            raise ValueError(f"duplicate rule_id: {rule.rule_id!r}")
        seen.add(rule.rule_id)

    return rules
