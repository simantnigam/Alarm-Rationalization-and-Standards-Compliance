"""iso_z must never contain a literal '+' -- that character is misread as a space once
a client (e.g. the supplied Postman chaining collection) echoes the value back into a
URL query string (CHAIN-02 caught this against a live server).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from alarm_api_simulator.timeutil import iso_z


def test_utc_datetime_uses_z_suffix() -> None:
    dt = datetime(2026, 6, 29, 0, 0, 0, tzinfo=UTC)
    assert iso_z(dt) == "2026-06-29T00:00:00Z"


def test_output_never_contains_a_plus_sign() -> None:
    dt = datetime(2026, 6, 29, 0, 0, 0, tzinfo=UTC)
    assert "+" not in iso_z(dt)


def test_non_utc_input_is_converted_to_utc_first() -> None:
    tz = timezone(timedelta(hours=5))
    dt = datetime(2026, 6, 29, 5, 0, 0, tzinfo=tz)
    assert iso_z(dt) == "2026-06-29T00:00:00Z"


def test_roundtrips_through_datetime_fromisoformat() -> None:
    dt = datetime(2026, 6, 29, 0, 7, 30, tzinfo=UTC)
    assert datetime.fromisoformat(iso_z(dt)) == dt
