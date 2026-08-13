"""Request/response schemas for the copilot HTTP API."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str
