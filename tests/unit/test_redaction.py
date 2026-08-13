"""Redaction must never leak Authorization / *token* / *key* / *secret* values -- through
flat fields, nested dicts and lists, or an exception logged as a value (01-architecture.md
§9 Observability; 02-phases.md Phase 1).
"""

import pytest

from copilot.observability.redaction import REDACTED, redact_event


@pytest.mark.parametrize(
    "key",
    [
        "Authorization",
        "authorization",
        "token",
        "access_token",
        "X-Api-Key",
        "api_key",
        "client_secret",
        "SECRET",
    ],
)
def test_flat_sensitive_key_is_redacted(key: str) -> None:
    event = redact_event(None, "info", {key: "Bearer super-secret-value"})
    assert event[key] == REDACTED


def test_nested_dict_values_are_redacted() -> None:
    event = redact_event(
        None,
        "info",
        {
            "request": {
                "headers": {"Authorization": "Bearer abc123", "x-client-id": "postman-client"},
                "body": {"nested": {"api_key": "sk-should-not-appear"}},
            }
        },
    )
    headers = event["request"]["headers"]
    assert headers["Authorization"] == REDACTED
    assert headers["x-client-id"] == "postman-client"
    assert event["request"]["body"]["nested"]["api_key"] == REDACTED


def test_list_of_dicts_is_redacted() -> None:
    event = redact_event(
        None,
        "info",
        {"calls": [{"token": "abc"}, {"trace_id": "trace-1"}]},
    )
    assert event["calls"][0]["token"] == REDACTED
    assert event["calls"][1]["trace_id"] == "trace-1"


def test_non_sensitive_keys_pass_through_unchanged() -> None:
    event = redact_event(
        None,
        "info",
        {"trace_id": "trace-1", "conversation_id": "conv-1", "duration_ms": 42.0},
    )
    assert event == {"trace_id": "trace-1", "conversation_id": "conv-1", "duration_ms": 42.0}


def test_exception_value_with_embedded_token_is_scrubbed() -> None:
    exc = ValueError("auth failed: token=abc123secret while calling upstream")
    event = redact_event(None, "error", {"error": exc})
    assert "abc123secret" not in event["error"]
    assert "ValueError" in event["error"]


def test_exception_args_containing_a_sensitive_dict_are_redacted() -> None:
    exc = RuntimeError({"Authorization": "Bearer abc123", "detail": "upstream 401"})
    event = redact_event(None, "error", {"error": exc})
    assert "abc123" not in event["error"]


def test_deeply_nested_structure_is_fully_redacted() -> None:
    event = redact_event(
        None,
        "info",
        {"a": {"b": {"c": [{"d": {"secret": "leak-me"}}]}}},
    )
    assert event["a"]["b"]["c"][0]["d"]["secret"] == REDACTED
