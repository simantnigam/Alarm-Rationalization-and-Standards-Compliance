"""_iter_sse_events: the GUI's only parsing logic, and the only piece of the frontend
that's meaningfully unit-testable without a browser (L-14)."""

from __future__ import annotations

from frontend.api_client import _iter_sse_events


def test_parses_a_single_event() -> None:
    lines = iter(["event: tool", 'data: {"tool_name": "search_assets"}', ""])
    events = list(_iter_sse_events(lines))
    assert events == [{"event": "tool", "data": {"tool_name": "search_assets"}}]


def test_parses_multiple_events_in_sequence() -> None:
    lines = iter(
        [
            "event: tool",
            'data: {"ok": true}',
            "",
            "event: citation",
            'data: {"doc_id": "ALM-PHIL-001"}',
            "",
            "event: done",
            'data: {"answer": "hello"}',
            "",
        ]
    )
    events = list(_iter_sse_events(lines))
    assert [e["event"] for e in events] == ["tool", "citation", "done"]
    assert events[2]["data"]["answer"] == "hello"


def test_incomplete_trailing_event_is_dropped_not_raised() -> None:
    lines = iter(["event: tool", 'data: {"ok": true}'])  # no trailing blank line
    events = list(_iter_sse_events(lines))
    assert events == []
