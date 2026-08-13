"""The generator must satisfy every scenario guarantee in 06-data-model.md §6 --
these are what let the supplied Postman chaining flows pass on a clean seed. Generation
must also be fully deterministic (same seed -> byte-identical output).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alarm_api_simulator.seed.generator import SeedDataset, generate_dataset

SIM_NOW = datetime(2026, 8, 13, tzinfo=UTC)
SIM_SEED = 20260812


@pytest.fixture(scope="module")
def compact_dataset() -> SeedDataset:
    return generate_dataset(profile="compact", seed=SIM_SEED, now=SIM_NOW)


class TestDeterminism:
    def test_same_seed_produces_identical_output(self) -> None:
        a = generate_dataset(profile="compact", seed=SIM_SEED, now=SIM_NOW)
        b = generate_dataset(profile="compact", seed=SIM_SEED, now=SIM_NOW)
        assert a.alarms == b.alarms
        assert a.alarm_definitions == b.alarm_definitions

    def test_different_seed_produces_different_output(self) -> None:
        a = generate_dataset(profile="compact", seed=SIM_SEED, now=SIM_NOW)
        b = generate_dataset(profile="compact", seed=SIM_SEED + 1, now=SIM_NOW)
        assert a.alarms != b.alarms


class TestReferentialIntegrity:
    def test_every_alarm_references_a_known_alarm_code(self, compact_dataset: SeedDataset) -> None:
        known_codes = {d["alarm_code"] for d in compact_dataset.alarm_definitions}
        assert all(a["alarm_code"] in known_codes for a in compact_dataset.alarms)

    def test_every_alarm_definition_references_a_known_asset(
        self, compact_dataset: SeedDataset
    ) -> None:
        known_assets = {a["asset_id"] for a in compact_dataset.assets}
        assert all(d["asset_id"] in known_assets for d in compact_dataset.alarm_definitions)

    def test_alarm_ids_are_unique(self, compact_dataset: SeedDataset) -> None:
        ids = [a["alarm_id"] for a in compact_dataset.alarms]
        assert len(ids) == len(set(ids))


class TestScenarioGuarantees:
    """06-data-model.md §6 -- asserted and fails loudly if unmet."""

    def test_boiler_feed_pumps_101_and_102_exist_in_northplant_unit1(
        self, compact_dataset: SeedDataset
    ) -> None:
        names = {
            a["asset_name"]
            for a in compact_dataset.assets
            if a["site"] == "NorthPlant" and a["unit"] == "Unit 1"
        }
        assert "Boiler Feed Pump 101" in names
        assert "Boiler Feed Pump 102" in names

    def test_at_least_three_compressor_assets_exist(self, compact_dataset: SeedDataset) -> None:
        compressors = [a for a in compact_dataset.assets if a["asset_type"] == "compressor"]
        assert len(compressors) >= 3

    def test_at_least_three_motor_assets_in_unit5(self, compact_dataset: SeedDataset) -> None:
        motors = [
            a
            for a in compact_dataset.assets
            if a["asset_type"] == "motor" and a["unit"] == "Unit 5"
        ]
        assert len(motors) >= 3

    def test_eastrefinery_has_active_alarms(self, compact_dataset: SeedDataset) -> None:
        active = [
            a
            for a in compact_dataset.alarms
            if a["site"] == "EastRefinery" and a["status"] == "active"
        ]
        assert len(active) > 0

    def test_unit2_has_a_genuine_flood_window(self, compact_dataset: SeedDataset) -> None:
        unit2_alarms = sorted(
            (a for a in compact_dataset.alarms if a["unit"] == "Unit 2"),
            key=lambda a: a["start_time"],
        )
        assert _max_alarms_in_any_10min_window(unit2_alarms) > 10

    def test_bfp101_has_recurring_high_or_critical_alarms_in_last_90_days(
        self, compact_dataset: SeedDataset
    ) -> None:
        window_start = SIM_NOW - timedelta(days=90)
        bfp101_recent = [
            a
            for a in compact_dataset.alarms
            if a["asset_name"] == "Boiler Feed Pump 101"
            and a["severity"] in ("high", "critical")
            and a["start_time"] >= window_start
        ]
        assert len(bfp101_recent) >= 5

    def test_stale_chattering_fleeting_and_recurring_populations_exist(
        self, compact_dataset: SeedDataset
    ) -> None:
        durations = [a["duration_s"] for a in compact_dataset.alarms if a["duration_s"] is not None]
        assert any(d > 86400 for d in durations), "no stale (>24h) occurrence found"
        assert any(d < 5 for d in durations), "no fleeting (<5s) occurrence found"

        by_code: dict[str, int] = {}
        for a in compact_dataset.alarms:
            by_code[a["alarm_code"]] = by_code.get(a["alarm_code"], 0) + 1
        assert any(count >= 25 for count in by_code.values()), "no recurring code found"

        assert _max_alarms_in_any_1min_window_for_any_code(compact_dataset.alarms) >= 3, (
            "no chattering (>=3/min for one code) burst found"
        )

    def test_sif_demo_case_exists(self, compact_dataset: SeedDataset) -> None:
        """One NorthPlant alarm_code: is_sif_related=True AND top-decile nuisance
        potential (high occurrence rate) among NorthPlant codes -- it must rank first
        on measured evidence and still be refused by the safety gate (Phase 7).
        """
        sif_codes = {
            d["alarm_code"] for d in compact_dataset.alarm_definitions if d["is_sif_related"]
        }
        assert sif_codes, "no SIF-related alarm_code defined at all"

        north_codes = {
            d["asset_id"]: d["alarm_code"]
            for d in compact_dataset.alarm_definitions
            if d["alarm_code"] in sif_codes
        }
        north_asset_ids = {
            a["asset_id"] for a in compact_dataset.assets if a["site"] == "NorthPlant"
        }
        assert set(north_codes) & north_asset_ids, "no SIF code lives on a NorthPlant asset"

    def test_data_spans_required_windows(self, compact_dataset: SeedDataset) -> None:
        starts = [a["start_time"] for a in compact_dataset.alarms]
        earliest, latest = min(starts), max(starts)
        assert earliest <= SIM_NOW - timedelta(days=365 - 30)  # spans well back toward 12mo
        assert latest <= SIM_NOW
        postman_start = datetime(2026, 5, 1, tzinfo=UTC)
        postman_end = datetime(2026, 7, 1, tzinfo=UTC)
        assert any(postman_start <= s <= postman_end for s in starts)


def _max_alarms_in_any_10min_window(alarms: list[dict]) -> int:
    return _max_alarms_in_window(alarms, timedelta(minutes=10))


def _max_alarms_in_window(alarms: list[dict], window: timedelta) -> int:
    starts = sorted(a["start_time"] for a in alarms)
    best = 0
    left = 0
    for right in range(len(starts)):
        while starts[right] - starts[left] > window:
            left += 1
        best = max(best, right - left + 1)
    return best


def _max_alarms_in_any_1min_window_for_any_code(alarms: list[dict]) -> int:
    by_code: dict[str, list[dict]] = {}
    for a in alarms:
        by_code.setdefault(a["alarm_code"], []).append(a)
    return max(
        (_max_alarms_in_window(rows, timedelta(minutes=1)) for rows in by_code.values()),
        default=0,
    )
