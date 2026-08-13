"""Exponential backoff with full jitter (AWS Architecture Blog formula): spreads
retries out instead of a thundering herd, while staying bounded by `cap`."""

from __future__ import annotations

import random


def _ceiling(attempt: int, *, base: float, cap: float) -> float:
    return min(cap, base * (2**attempt))


def full_jitter_delay(attempt: int, *, base: float = 0.1, cap: float = 2.0) -> float:
    return random.uniform(0, _ceiling(attempt, base=base, cap=cap))
