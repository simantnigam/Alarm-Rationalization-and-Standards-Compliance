"""Thin HTTP client over the copilot API. Zero business logic -- parses SSE frames and
hands the caller typed event dicts; every rendering decision stays in app.py."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, TypedDict

import httpx


class ChatEvent(TypedDict):
    event: str
    data: dict[str, Any]


def _iter_sse_events(lines: Iterator[str]) -> Iterator[ChatEvent]:
    event_name: str | None = None
    data_line: str | None = None
    for line in lines:
        if line.startswith("event: "):
            event_name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            data_line = line.removeprefix("data: ")
        elif line == "" and event_name is not None and data_line is not None:
            yield ChatEvent(event=event_name, data=json.loads(data_line))
            event_name, data_line = None, None


def stream_chat(
    base_url: str,
    *,
    question: str,
    trace_id: str,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> Iterator[ChatEvent]:
    headers = {"trace_id": trace_id}
    if api_key:
        headers["X-API-Key"] = api_key

    with (
        httpx.Client(base_url=base_url, timeout=timeout) as client,
        client.stream(
            "POST", "/api/chat", json={"question": question}, headers=headers
        ) as response,
    ):
        response.raise_for_status()
        yield from _iter_sse_events(response.iter_lines())
