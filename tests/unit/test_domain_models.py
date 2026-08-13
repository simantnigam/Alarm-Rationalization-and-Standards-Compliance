"""Domain contract tests (Phase 1). These are the shared vocabulary every layer above
domain/ depends on -- validation rules here are load-bearing for the rest of the system.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from copilot.domain.alarm import (
    Alarm,
    AlarmSeverity,
    AlarmStatus,
    AlarmType,
    SafetyClassification,
    TimeRange,
)
from copilot.domain.asset import Asset, AssetType, Criticality, Site
from copilot.domain.candidate import CandidateCategory, RationalizationCandidate
from copilot.domain.citation import Citation
from copilot.domain.response import CopilotResponse
from copilot.domain.trace import ExecutionTrace, ToolInvocation
from copilot.domain.verdict import Verdict, VerdictStatus


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


class TestTimeRange:
    def test_valid_range_constructs(self) -> None:
        tr = TimeRange(start_time=_dt("2026-05-01"), end_time=_dt("2026-07-01"))
        assert tr.start_time < tr.end_time

    def test_start_after_end_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TimeRange(start_time=_dt("2026-07-01"), end_time=_dt("2026-05-01"))

    def test_equal_start_and_end_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TimeRange(start_time=_dt("2026-05-01"), end_time=_dt("2026-05-01"))


class TestSite:
    def test_site_requires_name(self) -> None:
        with pytest.raises(ValidationError):
            Site(name="")


class TestAsset:
    def test_minimal_asset_constructs(self) -> None:
        asset = Asset(
            asset_id="NP-U1-BFP-101",
            asset_name="Boiler Feed Pump 101",
            asset_type=AssetType.PUMP,
            site="NorthPlant",
            unit="Unit 1",
            criticality=Criticality.HIGH,
        )
        assert asset.asset_id == "NP-U1-BFP-101"
        assert asset.criticality is Criticality.HIGH

    def test_criticality_and_severity_are_distinct_types(self) -> None:
        # Criticality and AlarmSeverity share string values but are deliberately
        # separate enums -- a criticality must never be silently accepted where a
        # severity is expected, or vice versa.
        assert Criticality.HIGH.value == AlarmSeverity.HIGH.value
        assert Criticality.HIGH is not AlarmSeverity.HIGH  # type: ignore[comparison-overlap]


class TestAlarm:
    def _alarm(self, **overrides: object) -> Alarm:
        fields: dict[str, object] = {
            "alarm_id": "ALM-2026-000001",
            "alarm_code": "BFP101-VIB-HH",
            "asset_id": "NP-U1-BFP-101",
            "asset_name": "Boiler Feed Pump 101",
            "site": "NorthPlant",
            "unit": "Unit 1",
            "alarm_name": "Vibration High-High",
            "alarm_type": AlarmType.PROCESS,
            "severity": AlarmSeverity.HIGH,
            "is_sif_related": False,
            "safety_classification": SafetyClassification.NONE,
            "start_time": _dt("2026-05-01T00:00:00"),
            "status": AlarmStatus.CLEARED,
        }
        fields.update(overrides)
        return Alarm(**fields)  # type: ignore[arg-type]

    def test_minimal_alarm_constructs(self) -> None:
        alarm = self._alarm()
        assert alarm.status is AlarmStatus.CLEARED

    def test_severity_coerces_from_string(self) -> None:
        alarm = self._alarm(severity="critical")
        assert alarm.severity is AlarmSeverity.HIGH or alarm.severity is AlarmSeverity.CRITICAL
        assert alarm.severity is AlarmSeverity.CRITICAL

    def test_active_alarm_may_have_no_end_time(self) -> None:
        alarm = self._alarm(status=AlarmStatus.ACTIVE, end_time=None)
        assert alarm.end_time is None

    def test_end_time_before_start_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._alarm(
                start_time=_dt("2026-05-02T00:00:00"),
                end_time=_dt("2026-05-01T00:00:00"),
            )

    def test_sif_related_requires_non_none_classification(self) -> None:
        # is_sif_related=True with safety_classification=NONE is an inconsistent alarm
        # record -- the SIF gate (Phase 7) depends on this pair never drifting apart.
        with pytest.raises(ValidationError):
            self._alarm(is_sif_related=True, safety_classification=SafetyClassification.NONE)

    def test_sif_related_with_sif_classification_is_valid(self) -> None:
        alarm = self._alarm(is_sif_related=True, safety_classification=SafetyClassification.SIF)
        assert alarm.is_sif_related is True


class TestRationalizationCandidate:
    def _candidate(self, **overrides: object) -> RationalizationCandidate:
        fields: dict[str, object] = {
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
            "occurrences_per_day": 0.33,
            "stale_occurrences": 0,
            "max_stale_minutes": 0.0,
            "chatter_index": 2,
            "fleeting_count": 0,
            "fleeting_rate": 0.0,
            "avg_ack_delay_s": 45.0,
            "max_ack_delay_s": 120.0,
            "unacknowledged_rate": 0.1,
            "nuisance_score": 62.0,
            "category": CandidateCategory.RECURRING,
            "reason": "30 occurrences in 90 days exceeds the 25-occurrence threshold.",
        }
        fields.update(overrides)
        return RationalizationCandidate(**fields)  # type: ignore[arg-type]

    def test_minimal_candidate_constructs(self) -> None:
        candidate = self._candidate()
        assert candidate.category is CandidateCategory.RECURRING

    @pytest.mark.parametrize("bad_score", [-1.0, 100.1])
    def test_nuisance_score_out_of_bounds_rejected(self, bad_score: float) -> None:
        with pytest.raises(ValidationError):
            self._candidate(nuisance_score=bad_score)

    def test_negative_occurrences_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._candidate(occurrences=-1)

    @pytest.mark.parametrize("bad_rate", [-0.01, 1.01])
    def test_rate_fields_bounded_zero_to_one(self, bad_rate: float) -> None:
        with pytest.raises(ValidationError):
            self._candidate(unacknowledged_rate=bad_rate)


class TestCitation:
    def test_minimal_citation_constructs(self) -> None:
        citation = Citation(
            doc_id="ALM-CRIT-003",
            title="Suppression and Shelving Approval Criteria",
            version="3.0",
            clause_id="3.1",
            section_path="Eligibility Criteria",
            score=0.82,
            snippet="Minimum Occurrence Evidence: >=25 occurrences in the trailing 90 days.",
        )
        assert citation.doc_id == "ALM-CRIT-003"

    def test_rendered_citation_matches_expected_format(self) -> None:
        citation = Citation(
            doc_id="ALM-CRIT-003",
            title="Minimum Occurrence Evidence",
            version="3.0",
            clause_id="3.1",
            score=0.82,
            snippet="...",
        )
        assert citation.rendered() == '[ALM-CRIT-003 §3.1 "Minimum Occurrence Evidence" v3.0]'

    def test_rendered_citation_with_page_for_pdf_source(self) -> None:
        citation = Citation(
            doc_id="ALM-STD-002",
            title="Rationalization Trigger",
            version="1.4",
            clause_id="4.1",
            page=7,
            score=0.7,
            snippet="...",
        )
        assert citation.rendered() == '[ALM-STD-002 §4.1 p.7 "Rationalization Trigger" v1.4]'

    @pytest.mark.parametrize("bad_score", [-0.01, 1.01])
    def test_score_bounded_zero_to_one(self, bad_score: float) -> None:
        with pytest.raises(ValidationError):
            Citation(
                doc_id="ALM-CRIT-003",
                title="x",
                version="1.0",
                clause_id="1",
                score=bad_score,
                snippet="...",
            )


class TestVerdict:
    def test_verdict_constructs_with_clause_ref(self) -> None:
        verdict = Verdict(
            rule_id="SAF-001",
            doc_id="SAF-INST-005",
            clause_id="2.1",
            status=VerdictStatus.FAIL,
            measured=True,
            threshold=True,
            margin=None,
            message="SIF-linked alarms are ineligible for suppression.",
        )
        assert verdict.clause_ref == "SAF-INST-005 §2.1"
        assert verdict.status is VerdictStatus.FAIL

    def test_pass_status_accepted(self) -> None:
        verdict = Verdict(
            rule_id="SUP-001",
            doc_id="ALM-CRIT-003",
            clause_id="3.1",
            status=VerdictStatus.PASS,
            measured=30,
            threshold=25,
            margin=5,
            message="Meets minimum occurrence evidence.",
        )
        assert verdict.status is VerdictStatus.PASS


class TestToolInvocationAndTrace:
    def test_tool_invocation_records_outcome(self) -> None:
        inv = ToolInvocation(
            tool_name="search_assets",
            server="alarm-management",
            arguments={"query": "Boiler Feed Pump 101"},
            ok=True,
            result={"results": []},
            started_at=_dt("2026-08-13T00:00:00"),
            duration_ms=42.0,
            retry_count=0,
            trace_id="trace-001",
        )
        assert inv.ok is True
        assert inv.error_code is None

    def test_failed_invocation_requires_error_code(self) -> None:
        with pytest.raises(ValidationError):
            ToolInvocation(
                tool_name="search_assets",
                server="alarm-management",
                arguments={},
                ok=False,
                error_code=None,
                started_at=_dt("2026-08-13T00:00:00"),
                duration_ms=10.0,
                retry_count=0,
                trace_id="trace-001",
            )

    def test_execution_trace_aggregates_invocations(self) -> None:
        inv = ToolInvocation(
            tool_name="search_assets",
            server="alarm-management",
            arguments={},
            ok=True,
            started_at=_dt("2026-08-13T00:00:00"),
            duration_ms=5.0,
            retry_count=0,
            trace_id="trace-001",
        )
        trace = ExecutionTrace(
            conversation_id="conv-1",
            request_id="req-1",
            trace_id="trace-001",
            invocations=[inv],
        )
        assert len(trace.invocations) == 1


class TestCopilotResponse:
    def test_minimal_response_constructs(self) -> None:
        response = CopilotResponse(
            conversation_id="conv-1",
            question="Identify stale alarms in NorthPlant Unit 1.",
            answer="Two alarm codes exceed the stale threshold.",
            candidates=[],
            verdicts=[],
            citations=[],
            trace=ExecutionTrace(
                conversation_id="conv-1", request_id="req-1", trace_id="trace-1", invocations=[]
            ),
            degraded=False,
            evidence_gap=False,
        )
        assert response.degraded is False
        assert response.clarification is None

    def test_degraded_response_still_carries_partial_evidence(self) -> None:
        response = CopilotResponse(
            conversation_id="conv-1",
            question="Show recurring alarms for Unit 5.",
            answer="Partial results only; one data source was unavailable.",
            candidates=[],
            verdicts=[],
            citations=[],
            trace=ExecutionTrace(
                conversation_id="conv-1", request_id="req-1", trace_id="trace-1", invocations=[]
            ),
            degraded=True,
            evidence_gap=False,
        )
        assert response.degraded is True
