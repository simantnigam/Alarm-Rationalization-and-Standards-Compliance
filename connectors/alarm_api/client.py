"""Typed httpx.AsyncClient wrapper around the Alarm Management API. Imported only by
MCP servers -- never by the copilot (enforced by .importlinter + Postgres role
separation, see D-05). Per-request sessions to start (R-09); pool only if the E2E
measurements demand it.

02-phases.md Phase 3: retry with full jitter + Retry-After, trace propagation via
TraceContext, and the remaining 9 endpoint methods on top of the search_assets slice
built for the walking skeleton (Phase 2.5).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from connectors.alarm_api.backoff import full_jitter_delay
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
from connectors.alarm_api.models import (
    Alarm,
    AlarmListResponse,
    AssetSearchResponse,
    CandidatesResponse,
    CorrelationResponse,
    ExecuteCalculationResponse,
    FloodAnalysisResponse,
    GenerateCalculationResponse,
    OperatorRecommendationsResponse,
    SummaryResponse,
    TrendsResponse,
)
from connectors.alarm_api.trace import TraceContext

_T = TypeVar("_T", bound=BaseModel)
_logger = structlog.get_logger(__name__)

SleepFn = Callable[[float], Awaitable[None]]


async def _default_sleep(delay: float) -> None:
    import asyncio

    await asyncio.sleep(delay)


class AlarmApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        connect_timeout: float = 3.0,
        read_timeout: float = 15.0,
        total_timeout: float = 20.0,
        max_attempts: int = 3,
        backoff_base: float = 0.1,
        backoff_cap: float = 2.0,
        sleep_fn: SleepFn = _default_sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = httpx.Timeout(total_timeout, connect=connect_timeout, read=read_timeout)
        self.max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._sleep_fn = sleep_fn

    def _headers(self, trace: TraceContext | None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        if trace is not None:
            headers.update(trace.headers())
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        trace: TraceContext | None = None,
    ) -> httpx.Response:
        headers = self._headers(trace)

        for attempt in range(1, self.max_attempts + 1):
            is_last_attempt = attempt >= self.max_attempts
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url, timeout=self._timeout
                ) as http:
                    response = await http.request(
                        method, path, params=params, json=json_body, headers=headers
                    )
            except httpx.TimeoutException as exc:
                if is_last_attempt:
                    raise UpstreamTimeoutError(f"timed out calling {method} {path}") from exc
                await self._sleep_fn(
                    full_jitter_delay(attempt, base=self._backoff_base, cap=self._backoff_cap)
                )
                continue
            except httpx.TransportError as exc:
                if is_last_attempt:
                    raise UpstreamUnavailableError(
                        f"transport error calling {method} {path}"
                    ) from exc
                await self._sleep_fn(
                    full_jitter_delay(attempt, base=self._backoff_base, cap=self._backoff_cap)
                )
                continue

            if response.status_code == 429 and not is_last_attempt:
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after
                    else full_jitter_delay(attempt, base=self._backoff_base, cap=self._backoff_cap)
                )
                await self._sleep_fn(delay)
                continue
            if response.status_code >= 500 and not is_last_attempt:
                await self._sleep_fn(
                    full_jitter_delay(attempt, base=self._backoff_base, cap=self._backoff_cap)
                )
                continue

            return response

        raise UpstreamUnavailableError(
            f"exhausted retries calling {method} {path}"
        )  # pragma: no cover

    def _raise_for_status(self, response: httpx.Response) -> None:
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

    def _parse(self, response: httpx.Response, model: type[_T]) -> _T:
        try:
            return model.model_validate(response.json())
        except (PydanticValidationError, ValueError) as exc:
            raise ContractViolationError("response did not match the expected schema") from exc

    async def search_assets(
        self,
        *,
        query: str,
        limit: int = 20,
        unit: str | None = None,
        site: str | None = None,
        trace: TraceContext | None = None,
    ) -> AssetSearchResponse:
        params: dict[str, Any] = {"query": query, "limit": limit}
        if unit:
            params["unit"] = unit
        if site:
            params["site"] = site

        response = await self._request("GET", "/assets/search", params=params, trace=trace)
        self._raise_for_status(response)
        return self._parse(response, AssetSearchResponse)

    async def list_alarms(
        self,
        *,
        asset_id: str | None = None,
        unit: str | None = None,
        site: str | None = None,
        status: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "start_time",
        sort_order: str = "desc",
        trace: TraceContext | None = None,
    ) -> AlarmListResponse:
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        if asset_id:
            params["asset_id"] = asset_id
        if unit:
            params["unit"] = unit
        if site:
            params["site"] = site
        if status:
            params["status"] = status
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        response = await self._request("GET", "/alarms", params=params, trace=trace)
        self._raise_for_status(response)
        return self._parse(response, AlarmListResponse)

    async def paginate_alarms(
        self,
        *,
        max_pages: int = 20,
        page_size: int = 50,
        trace: TraceContext | None = None,
        **filters: Any,
    ) -> AsyncIterator[Alarm]:
        """A hard page cap that's surfaced (logged), never a silent truncation."""
        page = 1
        while True:
            response = await self.list_alarms(
                page=page, page_size=page_size, trace=trace, **filters
            )
            for alarm in response.data:
                yield alarm

            if not response.has_more:
                return
            if page >= max_pages:
                await _logger.awarning(
                    "alarm_pagination_truncated",
                    max_pages=max_pages,
                    page_size=page_size,
                    filters=filters,
                )
                return
            page += 1

    async def get_alarm_summary(
        self,
        *,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        severity: list[str] | None = None,
        alarm_types: list[str] | None = None,
        group_by: list[str] | None = None,
        kpis: list[str] | None = None,
        trace: TraceContext | None = None,
    ) -> SummaryResponse:
        body = _scope_body(
            asset_ids=asset_ids, unit=unit, site=site, start_time=start_time, end_time=end_time
        )
        if severity:
            body["severity"] = severity
        if alarm_types:
            body["alarm_types"] = alarm_types
        if group_by:
            body["group_by"] = group_by
        if kpis:
            body["kpis"] = kpis

        response = await self._request("POST", "/alarms/summary", json_body=body, trace=trace)
        self._raise_for_status(response)
        return self._parse(response, SummaryResponse)

    async def get_alarm_trends(
        self,
        *,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        bucket: str = "daily",
        metrics: list[str] | None = None,
        trace: TraceContext | None = None,
    ) -> TrendsResponse:
        body = _scope_body(
            asset_ids=asset_ids, unit=unit, site=site, start_time=start_time, end_time=end_time
        )
        body["bucket"] = bucket
        body["metrics"] = metrics or ["alarm_count"]

        response = await self._request("POST", "/alarms/trends", json_body=body, trace=trace)
        self._raise_for_status(response)
        return self._parse(response, TrendsResponse)

    async def analyze_alarm_flood(
        self,
        *,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        threshold_count: int = 10,
        rolling_window_minutes: float = 10,
        trace: TraceContext | None = None,
    ) -> FloodAnalysisResponse:
        body = _scope_body(unit=unit, site=site, start_time=start_time, end_time=end_time)
        body["threshold_count"] = threshold_count
        body["rolling_window_minutes"] = rolling_window_minutes

        response = await self._request(
            "POST", "/alarms/flood-analysis", json_body=body, trace=trace
        )
        self._raise_for_status(response)
        return self._parse(response, FloodAnalysisResponse)

    async def get_rationalization_candidates(
        self,
        *,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        recurrence_threshold: int = 25,
        stale_minutes_threshold: float = 1440,
        trace: TraceContext | None = None,
    ) -> CandidatesResponse:
        body = _scope_body(
            asset_ids=asset_ids, unit=unit, site=site, start_time=start_time, end_time=end_time
        )
        body["recurrence_threshold"] = recurrence_threshold
        body["stale_minutes_threshold"] = stale_minutes_threshold

        response = await self._request(
            "POST", "/alarms/rationalization-candidates", json_body=body, trace=trace
        )
        self._raise_for_status(response)
        return self._parse(response, CandidatesResponse)

    async def correlate_alarms(
        self,
        *,
        asset_ids: list[str] | None = None,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        correlation_method: str = "cooccurrence",
        lag_window_minutes: float = 15,
        severity_threshold: str = "medium",
        min_support: int = 1,
        trace: TraceContext | None = None,
    ) -> CorrelationResponse:
        body = _scope_body(
            asset_ids=asset_ids, unit=unit, site=site, start_time=start_time, end_time=end_time
        )
        body["correlation_method"] = correlation_method
        body["lag_window_minutes"] = lag_window_minutes
        body["severity_threshold"] = severity_threshold
        body["min_support"] = min_support

        response = await self._request("POST", "/alarms/correlation", json_body=body, trace=trace)
        self._raise_for_status(response)
        return self._parse(response, CorrelationResponse)

    async def get_operator_recommendations(
        self,
        *,
        alarm_id: str,
        include_related: bool = False,
        include_asset_context: bool = False,
        include_historical_pattern: bool = False,
        trace: TraceContext | None = None,
    ) -> OperatorRecommendationsResponse:
        body = {
            "alarm_id": alarm_id,
            "include_related": include_related,
            "include_asset_context": include_asset_context,
            "include_historical_pattern": include_historical_pattern,
        }
        response = await self._request(
            "POST", "/recommendations/operator-actions", json_body=body, trace=trace
        )
        self._raise_for_status(response)
        return self._parse(response, OperatorRecommendationsResponse)

    async def generate_kpi_calculation(
        self,
        *,
        calculation_type: str,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        trace: TraceContext | None = None,
    ) -> GenerateCalculationResponse:
        body = {
            "calculation_type": calculation_type,
            "filters": _calculation_filters(
                unit=unit, site=site, start_time=start_time, end_time=end_time
            ),
        }
        response = await self._request(
            "POST", "/calculation-code/generate", json_body=body, trace=trace
        )
        self._raise_for_status(response)
        return self._parse(response, GenerateCalculationResponse)

    async def execute_kpi_calculation(
        self,
        *,
        calculation_id: str,
        unit: str | None = None,
        site: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        trace: TraceContext | None = None,
    ) -> ExecuteCalculationResponse:
        body = {
            "calculation_id": calculation_id,
            "filters": _calculation_filters(
                unit=unit, site=site, start_time=start_time, end_time=end_time
            ),
        }
        response = await self._request(
            "POST", "/calculation-code/execute", json_body=body, trace=trace
        )
        self._raise_for_status(response)
        return self._parse(response, ExecuteCalculationResponse)


def _scope_body(
    *,
    asset_ids: list[str] | None = None,
    unit: str | None = None,
    site: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if asset_ids:
        body["asset_ids"] = asset_ids
    if unit:
        body["unit"] = unit
    if site:
        body["site"] = site
    if start_time and end_time:
        body["time_range"] = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
    return body


def _calculation_filters(
    *,
    unit: str | None,
    site: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if unit:
        filters["unit"] = unit
    if site:
        filters["site"] = site
    if start_time:
        filters["start_time"] = start_time.isoformat()
    if end_time:
        filters["end_time"] = end_time.isoformat()
    return filters
