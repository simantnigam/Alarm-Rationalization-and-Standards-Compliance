"""ToolInvocation and ExecutionTrace: the record of every MCP call an analysis makes,
rendered as the GUI's execution timeline (§4.6.f) and asserted against in tests
(trace_id propagation, partial-failure handling).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolInvocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str
    server: str
    arguments: dict[str, Any]
    ok: bool
    result: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    duration_ms: float = Field(ge=0)
    retry_count: int = Field(ge=0)
    trace_id: str

    @model_validator(mode="after")
    def _check_error_code_on_failure(self) -> ToolInvocation:
        if not self.ok and self.error_code is None:
            raise ValueError("a failed ToolInvocation (ok=False) must carry an error_code")
        return self


class ExecutionTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    request_id: str
    trace_id: str
    invocations: list[ToolInvocation]
