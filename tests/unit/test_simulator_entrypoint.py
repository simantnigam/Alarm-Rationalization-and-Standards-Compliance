"""resolve_sim_now: SIM_NOW pins the demo clock when set; otherwise real now() -- this
is what lets the demo dataset stay anchored to a fixed date across reseeds.
"""

from __future__ import annotations

from datetime import UTC, datetime

from alarm_api_simulator.__main__ import resolve_sim_now
from alarm_api_simulator.config import SimulatorSettings


def test_sim_now_pins_the_clock_when_set() -> None:
    settings = SimulatorSettings(
        alarm_api_token="t",
        alarmdb_password="p",
        sim_now="2026-08-13T00:00:00+00:00",
    )
    assert resolve_sim_now(settings) == datetime(2026, 8, 13, tzinfo=UTC)


def test_sim_now_defaults_to_real_now_when_unset() -> None:
    settings = SimulatorSettings(alarm_api_token="t", alarmdb_password="p", sim_now=None)
    before = datetime.now(UTC)
    resolved = resolve_sim_now(settings)
    after = datetime.now(UTC)
    assert before <= resolved <= after
