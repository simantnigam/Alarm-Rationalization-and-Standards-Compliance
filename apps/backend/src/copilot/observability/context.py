"""request_id / conversation_id / trace_id propagation, built on structlog's tested
contextvars machinery rather than reimplementing it (01-architecture.md §9).
"""

from __future__ import annotations

import structlog


def bind_request_context(
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Binds whichever identifiers are given so every subsequent log event in this
    context (until cleared) carries them. Omitted fields are left untouched.
    """
    values = {
        key: value
        for key, value in (
            ("request_id", request_id),
            ("conversation_id", conversation_id),
            ("trace_id", trace_id),
        )
        if value is not None
    }
    structlog.contextvars.bind_contextvars(**values)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
