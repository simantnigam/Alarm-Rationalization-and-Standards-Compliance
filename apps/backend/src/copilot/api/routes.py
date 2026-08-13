"""POST /api/chat (SSE: tool | citation | done) and GET /api/health. Walking-skeleton
slice (02-phases.md Phase 2.5); Phase 8 adds /api/tools, /api/conversations/{id}, the
X-API-Key dependency (A-06), and the approval_required event.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from copilot.api.schemas import ChatRequest
from copilot.api.sse import format_sse
from copilot.graph.state import CopilotState

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/chat")
async def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    graph = request.app.state.graph
    trace_id = request.headers.get("trace_id") or str(uuid.uuid4())
    conversation_id = body.conversation_id or str(uuid.uuid4())

    async def event_stream() -> AsyncIterator[str]:
        initial_state: CopilotState = {
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "question": body.question,
            "plan": None,
            "invocations": [],
            "citations": [],
            "answer": "",
        }
        result = await graph.ainvoke(initial_state)

        for invocation in result["invocations"]:
            yield format_sse(
                "tool",
                {
                    "tool_name": invocation.tool_name,
                    "server": invocation.server,
                    "ok": invocation.ok,
                    "duration_ms": invocation.duration_ms,
                    "trace_id": invocation.trace_id,
                },
            )
        for citation in result["citations"]:
            yield format_sse(
                "citation",
                {
                    "doc_id": citation.doc_id,
                    "clause_id": citation.clause_id,
                    "rendered": citation.rendered(),
                    "score": citation.score,
                },
            )
        yield format_sse(
            "done",
            {
                "answer": result["answer"],
                "conversation_id": conversation_id,
                "trace_id": trace_id,
            },
        )

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers={"trace_id": trace_id}
    )
