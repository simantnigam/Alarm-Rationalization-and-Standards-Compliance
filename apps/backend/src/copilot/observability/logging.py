"""structlog configuration: JSON output, bound request/conversation/trace context on
every event, and redaction applied before anything is rendered.
"""

from __future__ import annotations

import logging
import sys

import structlog

from copilot.observability.redaction import redact_event


def configure_logging(level: str = "INFO") -> None:
    # force=True + an explicit stdout stream: idempotent across repeated calls (each
    # test run reconfigures cleanly) and JSON lines land on stdout for log collection.
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_event,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
