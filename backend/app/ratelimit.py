"""Tiny in-process sliding-window limiter for the few public (unauthenticated) endpoints. Per process; enough for a pilot."""

from __future__ import annotations

import time
from collections import defaultdict, deque

_hits: dict[str, deque[float]] = defaultdict(deque)


def allow(key: str, limit: int, window_s: float) -> bool:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def reset() -> None:
    _hits.clear()
