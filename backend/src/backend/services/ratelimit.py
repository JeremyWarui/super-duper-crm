"""A per-client limit on how often a public form may be sent, kept in this process's memory."""

import time
from collections import defaultdict, deque


class RateLimit:
    """At most `limit` hits per `window` seconds for each key; each process counts its own."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        for stale in [k for k, h in self._hits.items() if h and now - h[-1] > self.window]:
            del self._hits[stale]
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True
