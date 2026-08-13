"""full_jitter_delay: AWS-style full jitter -- bounded, non-negative, and grows with
attempt number so retries actually spread out rather than thundering-herd."""

from __future__ import annotations

from connectors.alarm_api.backoff import full_jitter_delay


def test_delay_is_never_negative() -> None:
    for attempt in range(1, 6):
        assert full_jitter_delay(attempt, base=0.1, cap=2.0) >= 0


def test_delay_never_exceeds_the_cap() -> None:
    for attempt in range(1, 10):
        assert full_jitter_delay(attempt, base=0.1, cap=2.0) <= 2.0


def test_higher_attempt_numbers_have_a_higher_ceiling() -> None:
    # Not a statistical test (full jitter is random) -- just that the *possible* upper
    # bound grows monotonically with attempt, up to the cap.
    import connectors.alarm_api.backoff as backoff_module

    assert backoff_module._ceiling(1, base=0.1, cap=2.0) < backoff_module._ceiling(
        4, base=0.1, cap=2.0
    )
