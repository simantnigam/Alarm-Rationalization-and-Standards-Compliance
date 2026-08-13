"""Error taxonomy for the Alarm Management API connector (01-architecture.md §4).
Every error carries a message safe to log -- never the token, never raw response body
text that might contain one.
"""

from __future__ import annotations


class AlarmApiError(Exception):
    """Base class for every error this connector raises."""


class AuthError(AlarmApiError):
    """401 / 403 -- never includes the presented token."""


class NotFoundError(AlarmApiError):
    """404."""


class ValidationError(AlarmApiError):
    """422 -- the request was rejected by the upstream API."""


class RateLimitError(AlarmApiError):
    """429, post-retry. Carries retry_after when the upstream provided one."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class UpstreamUnavailableError(AlarmApiError):
    """5xx, post-retry."""


class UpstreamTimeoutError(AlarmApiError):
    """Connect or read timeout, post-retry."""


class ContractViolationError(AlarmApiError):
    """The response body didn't match the expected shape."""
