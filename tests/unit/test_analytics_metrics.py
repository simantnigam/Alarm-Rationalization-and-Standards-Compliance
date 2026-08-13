"""nuisance_score and priority_score are deterministic and documented (06-data-model.md
§4.1-4.2) so the copilot can cite the formula rather than assert the number.
"""

import pytest

from alarm_api_simulator.analytics.metrics import (
    nuisance_score,
    priority_score,
    priority_score_factors,
)


class TestNuisanceScore:
    def test_all_zero_inputs_score_zero(self) -> None:
        assert (
            nuisance_score(
                occurrences_per_day=0, chatter_index=0, fleeting_rate=0, unacknowledged_rate=0
            )
            == 0
        )

    def test_all_maxed_inputs_score_100(self) -> None:
        assert (
            nuisance_score(
                occurrences_per_day=10,
                chatter_index=6,
                fleeting_rate=1.0,
                unacknowledged_rate=1.0,
            )
            == 100
        )

    def test_half_maxed_inputs_score_50(self) -> None:
        assert (
            nuisance_score(
                occurrences_per_day=5,
                chatter_index=3,
                fleeting_rate=0.5,
                unacknowledged_rate=0.5,
            )
            == 50
        )

    def test_occurrences_per_day_clamps_above_target(self) -> None:
        # 20/day is double the 10/day cap -- frequency component must still max at 40.
        low = nuisance_score(
            occurrences_per_day=10, chatter_index=0, fleeting_rate=0, unacknowledged_rate=0
        )
        high = nuisance_score(
            occurrences_per_day=20, chatter_index=0, fleeting_rate=0, unacknowledged_rate=0
        )
        assert low == high == 40

    def test_result_is_bounded_zero_to_100(self) -> None:
        score = nuisance_score(
            occurrences_per_day=1000, chatter_index=1000, fleeting_rate=1.0, unacknowledged_rate=1.0
        )
        assert 0 <= score <= 100


class TestPriorityScore:
    def test_low_everything_with_slow_response_time(self) -> None:
        # severity_w=10*0.45=4.5, criticality_w=10*0.25=2.5, urgency=(600/600)*100*0.30=30 -> 37
        score = priority_score(
            severity="low",
            criticality="low",
            allowable_response_time_s=600,
            is_sif_related=False,
        )
        assert score == 37

    def test_critical_everything_with_fast_response_time_caps_at_100(self) -> None:
        score = priority_score(
            severity="critical",
            criticality="critical",
            allowable_response_time_s=60,
            is_sif_related=False,
        )
        assert score == 100

    def test_sif_related_forces_a_minimum_floor_of_90(self) -> None:
        # Deliberately low inputs -- the SIF floor must still dominate.
        score = priority_score(
            severity="low",
            criticality="low",
            allowable_response_time_s=6000,
            is_sif_related=True,
        )
        assert score >= 90

    def test_non_sif_related_is_not_floored(self) -> None:
        score = priority_score(
            severity="low",
            criticality="low",
            allowable_response_time_s=6000,
            is_sif_related=False,
        )
        assert score < 90

    @pytest.mark.parametrize("bad_severity", ["urgent", "", "HIGH"])
    def test_unknown_severity_rejected(self, bad_severity: str) -> None:
        with pytest.raises(ValueError):
            priority_score(
                severity=bad_severity,
                criticality="low",
                allowable_response_time_s=600,
                is_sif_related=False,
            )


class TestPriorityScoreFactors:
    def test_factors_sum_to_the_same_score_and_are_explainable(self) -> None:
        result = priority_score_factors(
            severity="high",
            criticality="high",
            allowable_response_time_s=300,
            is_sif_related=False,
        )
        assert result["score"] == priority_score(
            severity="high",
            criticality="high",
            allowable_response_time_s=300,
            is_sif_related=False,
        )
        names = {f["name"] for f in result["factors"]}
        assert names == {"severity", "criticality", "urgency"}
        total_contribution = round(sum(f["contribution"] for f in result["factors"]))
        assert total_contribution == result["score"]

    def test_sif_floor_is_visible_as_a_separate_note(self) -> None:
        result = priority_score_factors(
            severity="low", criticality="low", allowable_response_time_s=6000, is_sif_related=True
        )
        assert result["score"] >= 90
        # The raw factor contributions alone would not reach 90 -- the SIF floor is
        # what did, and that must be visible rather than silently absorbed.
        raw_total = sum(f["contribution"] for f in result["factors"])
        assert raw_total < 90
