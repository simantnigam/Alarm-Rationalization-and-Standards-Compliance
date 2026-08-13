"""Typed httpx.AsyncClient wrapper around the Alarm Management API. Imported only by
MCP servers -- never by the copilot (enforced by .importlinter + Postgres role
separation, see D-05). Per-request sessions to start (R-09); pool only if the E2E
measurements demand it.

This is the first slice (search_assets only), built for the walking skeleton
(02-phases.md Phase 2.5). Phase 3 adds the remaining endpoints, retry with jitter, and
pagination on top of the same client -- unchanged here.
"""

from __future__ import annotations

import httpx
from pydantic import ValidationError as PydanticValidationError

from connectors.alarm_api.errors import (
    AlarmApiError,
    AuthError,
    ContractViolationError,
    NotFoundError,
    RateLimitError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from connectors.alarm_api.errors import ValidationError as UpstreamValidationError
from connectors.alarm_api.models import AssetSearchResponse


class AlarmApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        connect_timeout: float = 3.0,
        read_timeout: float = 15.0,
        total_timeout: float = 20.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = httpx.Timeout(total_timeout, connect=connect_timeout, read=read_timeout)

    def _headers(self, *, trace_id: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        if trace_id:
            headers["trace_id"] = trace_id
        return headers

    async def search_assets(
        self,
        *,
        query: str,
        limit: int = 20,
        unit: str | None = None,
        site: str | None = None,
        trace_id: str | None = None,
    ) -> AssetSearchResponse:
        params: dict[str, str | int] = {"query": query, "limit": limit}
        if unit:
            params["unit"] = unit
        if site:
            params["site"] = site

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as http:
            try:
                response = await http.get(
                    "/assets/search", params=params, headers=self._headers(trace_id=trace_id)
                )
            except httpx.TimeoutException as exc:
                raise UpstreamTimeoutError("timed out calling GET /assets/search") from exc
            except httpx.TransportError as exc:
                raise UpstreamUnavailableError(
                    "transport error calling GET /assets/search"
                ) from exc

        return self._parse_search_response(response)

    def _parse_search_response(self, response: httpx.Response) -> AssetSearchResponse:
        if response.status_code in (401, 403):
            raise AuthError("authentication failed")  # never includes the token
        if response.status_code == 404:
            raise NotFoundError("resource not found")
        if response.status_code == 422:
            raise UpstreamValidationError("request rejected by upstream")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "rate limited", retry_after=float(retry_after) if retry_after else None
            )
        if response.status_code >= 500:
            raise UpstreamUnavailableError(f"upstream returned {response.status_code}")
        if response.status_code != 200:
            raise AlarmApiError(f"unexpected status {response.status_code}")

        try:
            return AssetSearchResponse.model_validate(response.json())
        except (PydanticValidationError, ValueError) as exc:
            raise ContractViolationError("response did not match the expected schema") from exc
