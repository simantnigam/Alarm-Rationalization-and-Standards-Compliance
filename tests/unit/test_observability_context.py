"""request_id / conversation_id / trace_id must propagate into every log event emitted
while bound, and must not leak into events emitted after being cleared.
"""

import structlog

from copilot.observability.context import bind_request_context, clear_request_context


def test_bound_context_appears_in_log_event() -> None:
    clear_request_context()
    bind_request_context(request_id="req-1", conversation_id="conv-1", trace_id="trace-1")
    try:
        event = structlog.contextvars.get_contextvars()
        assert event["request_id"] == "req-1"
        assert event["conversation_id"] == "conv-1"
        assert event["trace_id"] == "trace-1"
    finally:
        clear_request_context()


def test_clear_request_context_removes_all_bound_values() -> None:
    bind_request_context(request_id="req-1", conversation_id="conv-1", trace_id="trace-1")
    clear_request_context()
    assert structlog.contextvars.get_contextvars() == {}


def test_partial_binding_leaves_other_fields_unset() -> None:
    clear_request_context()
    bind_request_context(request_id="req-2")
    try:
        event = structlog.contextvars.get_contextvars()
        assert event["request_id"] == "req-2"
        assert "conversation_id" not in event
    finally:
        clear_request_context()
