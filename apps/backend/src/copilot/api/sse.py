"""Server-Sent Events formatting for POST /api/chat (§2.2 "Displaying MCP execution
details in the GUI"). Walking-skeleton slice (02-phases.md Phase 2.5): the graph runs
to completion, then `tool`, `citation`, and `done` events are emitted from the result --
matching R-08's own conclusion that the trace/citations render after the run, not live.
"""

from __future__ import annotations

import json
from typing import Any


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
