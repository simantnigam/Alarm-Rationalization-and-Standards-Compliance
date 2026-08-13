"""Redaction processor: no log event may leak an Authorization header, a token, an API
key, or a secret -- through flat fields, arbitrarily nested dicts/lists, or an exception
value's message (01-architecture.md §9).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping
from typing import Any

REDACTED = "***REDACTED***"

# Deliberately broad: *key* also catches things like "retry_key" that aren't secrets.
# That false-positive is the accepted trade for zero false-negatives on real secrets.
_SENSITIVE_KEY_PATTERN = re.compile(r"(authorization|token|key|secret|password)", re.IGNORECASE)

# Scrubs "token=abc123", "key: abc123", etc. inside free text such as an exception
# message or a formatted traceback, where the sensitive part is a key-value pair
# rather than a whole structured value.
_INLINE_LEAK_PATTERN = re.compile(
    r"(?i)\b(authorization|token|api[_-]?key|secret|password)(['\"]?\s*[:=]\s*)"
    r"([^\s,;}'\"]+)"
)


def _is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY_PATTERN.search(key))


def _scrub_free_text(text: str) -> str:
    return _INLINE_LEAK_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (REDACTED if _is_sensitive_key(str(key)) else _redact_value(val))
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(item) for item in value)
    if isinstance(value, BaseException):
        if value.args:
            scrubbed_args = _redact_value(list(value.args))
            detail = ", ".join(str(arg) for arg in scrubbed_args)
        else:
            detail = _scrub_free_text(str(value))
        return f"{type(value).__name__}: {detail}"
    if isinstance(value, str):
        return _scrub_free_text(value)
    return value


def redact_event(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """A structlog processor: redacts every sensitive key in `event_dict`, recursively."""
    return {
        key: (REDACTED if _is_sensitive_key(str(key)) else _redact_value(val))
        for key, val in event_dict.items()
    }
