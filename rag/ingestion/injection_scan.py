"""Heuristic prompt-injection detection at ingest time (01-architecture.md §6,
07-rag-corpus.md §3's poisoned `SEC-TEST-999` fixture). A flagged chunk is still
embedded and stored -- so it can be reported in the ingest summary -- but is always
excluded from retrieval via a mandatory query-time filter (rag/retrieval/service.py).
"""

from __future__ import annotations

import re

_ZERO_WIDTH = {"​", "‌", "‍", "﻿"}

_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(the\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(
        r"disregard\s+(all\s+)?(the\s+)?(previous|prior)\s+(instructions|rules)", re.IGNORECASE
    ),
    re.compile(r"^\s*system\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*assistant\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"<tool_call>|\"name\"\s*:\s*\"\w+\"\s*,\s*\"arguments\"\s*:", re.IGNORECASE),
]


def scan_for_injection(text: str) -> bool:
    """True if `text` shows signs of a prompt-injection attempt: an instruction-override
    phrase, `system:`/`assistant:` role-spoofing, a tool-call-shaped string, or a
    zero-width character (a common evasion trick against naive keyword filters, so
    matching is done on the text with zero-width characters stripped -- the character's
    mere presence is itself flagged too, regardless of what it's hiding).
    """
    if any(c in _ZERO_WIDTH for c in text):
        return True
    cleaned = "".join(c for c in text if c not in _ZERO_WIDTH)
    return any(pattern.search(cleaned) for pattern in _PATTERNS)
