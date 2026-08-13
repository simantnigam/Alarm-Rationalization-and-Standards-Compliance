"""Topology is derived from the Postman chaining collection, not invented
(06-data-model.md §2) -- these tests pin the facts the chaining flows depend on.
"""

from alarm_api_simulator.seed.identifiers import alarm_code, alarm_id, asset_id, asset_tag
from alarm_api_simulator.seed.topology import TOPOLOGY, UnitProfile


def test_topology_has_three_sites_five_units() -> None:
    sites = {u.site for u in TOPOLOGY}
    units = {(u.site, u.unit) for u in TOPOLOGY}
    assert sites == {"NorthPlant", "SouthPlant", "EastRefinery"}
    assert len(units) == 5


def test_northplant_unit1_is_pump_heavy_and_has_boiler_feed_pumps() -> None:
    unit1 = next(u for u in TOPOLOGY if u.site == "NorthPlant" and u.unit == "Unit 1")
    assert "Boiler Feed Pump 101" in unit1.asset_names
    assert "Boiler Feed Pump 102" in unit1.asset_names
    bfp101 = next(a for a in unit1.assets if a.name == "Boiler Feed Pump 101")
    assert bfp101.tag_prefix == "BFP"
    assert bfp101.seq == 101
    assert bfp101.asset_type == "pump"


def test_southplant_unit3_has_at_least_three_compressors() -> None:
    unit3 = next(u for u in TOPOLOGY if u.site == "SouthPlant" and u.unit == "Unit 3")
    compressors = [a for a in unit3.assets if a.asset_type == "compressor"]
    assert len(compressors) >= 3


def test_eastrefinery_unit5_has_at_least_three_motors() -> None:
    unit5 = next(u for u in TOPOLOGY if u.site == "EastRefinery" and u.unit == "Unit 5")
    motors = [a for a in unit5.assets if a.asset_type == "motor"]
    assert len(motors) >= 3


def test_unit_profile_is_frozen_and_hashable() -> None:
    unit1 = next(u for u in TOPOLOGY if u.site == "NorthPlant" and u.unit == "Unit 1")
    assert isinstance(unit1, UnitProfile)
    hash(unit1)  # must not raise


def test_asset_ids_are_globally_unique_across_topology() -> None:
    ids = [
        asset_id(site=u.site, unit=u.unit, tag_prefix=a.tag_prefix, seq=a.seq)
        for u in TOPOLOGY
        for a in u.assets
    ]
    assert len(ids) == len(set(ids))


class TestIdentifiers:
    def test_asset_tag_format(self) -> None:
        assert asset_tag(tag_prefix="BFP", seq=101) == "BFP101"

    def test_asset_id_format(self) -> None:
        assert (
            asset_id(site="NorthPlant", unit="Unit 1", tag_prefix="BFP", seq=101) == "NP-U1-BFP-101"
        )

    def test_asset_id_is_deterministic(self) -> None:
        a = asset_id(site="EastRefinery", unit="Unit 5", tag_prefix="MTR", seq=7)
        b = asset_id(site="EastRefinery", unit="Unit 5", tag_prefix="MTR", seq=7)
        assert a == b

    def test_alarm_code_format(self) -> None:
        assert (
            alarm_code(tag_prefix="BFP", seq=101, measurement="VIB", condition="HH")
            == "BFP101-VIB-HH"
        )

    def test_alarm_id_format(self) -> None:
        assert alarm_id(year=2026, seq=1) == "ALM-2026-000001"

    def test_alarm_id_sequence_is_zero_padded(self) -> None:
        assert alarm_id(year=2026, seq=123456) == "ALM-2026-123456"
