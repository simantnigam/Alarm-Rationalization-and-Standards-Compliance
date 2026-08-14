"""The deterministic compliance rule engine (01-architecture.md §7, 02-phases.md
Phase 7). Pure -- no I/O, no LLM; a Verdict is never produced by a model (D-07). Every
applicable rule is evaluated independently and returned -- the engine never short-
circuits on a FAIL, so the audit trail always shows every criterion that was checked,
not just the first one that mattered.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping
from typing import Any

from copilot.compliance.rules import Rule
from copilot.domain.candidate import RationalizationCandidate
from copilot.domain.verdict import MeasuredValue, Verdict, VerdictStatus

_MISSING = object()

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}

_MARGIN_OPS = {">=", ">"}
_INVERSE_MARGIN_OPS = {"<=", "<"}


def evaluate(
    candidate: RationalizationCandidate,
    rules: list[Rule],
    evidence: Mapping[str, Any] | None = None,
) -> list[Verdict]:
    """Every rule whose `applies_to.site_scope` matches the candidate's site (or is
    `ALL`) is evaluated; a rule that doesn't apply produces no verdict at all -- it's
    never silently PASSed. `evidence` is an optional fallback metrics source, checked
    when a rule's predicate.metric isn't a field on `candidate` -- a missing metric
    (on both) always yields NEEDS_REVIEW, never a silent PASS.
    """
    verdicts = []
    for rule in rules:
        if not _applies(rule, candidate):
            continue
        verdicts.append(_evaluate_rule(rule, candidate, evidence or {}))
    return verdicts


def _applies(rule: Rule, candidate: RationalizationCandidate) -> bool:
    scope = rule.applies_to.site_scope
    return scope == "ALL" or scope == candidate.site


def _resolve_metric(
    metric: str, candidate: RationalizationCandidate, evidence: Mapping[str, Any]
) -> Any:
    value = getattr(candidate, metric, _MISSING)
    if value is not _MISSING:
        return value
    return evidence.get(metric, _MISSING)


def _margin(op: str, measured: MeasuredValue, threshold: MeasuredValue) -> float | None:
    if isinstance(measured, bool) or isinstance(threshold, bool):
        return None
    if not isinstance(measured, int | float) or not isinstance(threshold, int | float):
        return None
    if op in _MARGIN_OPS:
        return float(measured) - float(threshold)
    if op in _INVERSE_MARGIN_OPS:
        return float(threshold) - float(measured)
    return None


def _evaluate_rule(
    rule: Rule, candidate: RationalizationCandidate, evidence: Mapping[str, Any]
) -> Verdict:
    predicate = rule.predicate
    measured = _resolve_metric(predicate.metric, candidate, evidence)

    if measured is _MISSING:
        return Verdict(
            rule_id=rule.rule_id,
            alarm_code=candidate.alarm_code,
            doc_id=rule.source.doc_id,
            clause_id=rule.source.clause_id,
            status=VerdictStatus.NEEDS_REVIEW,
            measured=None,
            threshold=predicate.value,
            margin=None,
            message=f"metric {predicate.metric!r} unavailable for evaluation",
            overriding=rule.overriding,
        )

    predicate_true = _OPS[predicate.op](measured, predicate.value)

    if rule.outcome_when_true is not None:
        status = rule.outcome_when_true if predicate_true else VerdictStatus.PASS
    else:
        assert rule.outcome_when_false is not None  # Rule enforces exactly one is set
        status = VerdictStatus.PASS if predicate_true else rule.outcome_when_false

    return Verdict(
        rule_id=rule.rule_id,
        alarm_code=candidate.alarm_code,
        doc_id=rule.source.doc_id,
        clause_id=rule.source.clause_id,
        status=status,
        measured=measured,
        threshold=predicate.value,
        margin=_margin(predicate.op, measured, predicate.value),
        message=rule.message,
        overriding=rule.overriding,
    )
