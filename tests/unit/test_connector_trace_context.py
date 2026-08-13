"""TraceContext: the connector's trace propagation primitive (01-architecture.md §4,
§9). Every field is optional and independently omittable from the outgoing headers.
"""

from __future__ import annotations

from connectors.alarm_api.trace import TraceContext


def test_all_fields_present() -> None:
    ctx = TraceContext(trace_id="trace-1", client_id="client-1", metadata_tag="tag-1")
    assert ctx.headers() == {
        "trace_id": "trace-1",
        "x-client-id": "client-1",
        "x-metadata-tag": "tag-1",
    }


def test_only_trace_id_set() -> None:
    ctx = TraceContext(trace_id="trace-1")
    assert ctx.headers() == {"trace_id": "trace-1"}


def test_empty_context_produces_no_headers() -> None:
    assert TraceContext().headers() == {}
