"""In-process query latency tracking for the dashboard metric row.

A small ring buffer of the most recent query durations. Deliberately not
persisted: it exists so the demo dashboard can show a real, honest
"average query response time" for the running process without a schema
addition or migration. Reset on restart — which is the correct behaviour
for a live-demo metric.
"""

from __future__ import annotations

from collections import deque
from threading import Lock

_MAX_QUERIES = 200

_times: deque[float] = deque(maxlen=_MAX_QUERIES)
_lock = Lock()


def record_query(duration_ms: float) -> None:
    with _lock:
        _times.append(duration_ms)


def average_query_ms() -> float | None:
    with _lock:
        if not _times:
            return None
        return round(sum(_times) / len(_times), 1)


def queries_served() -> int:
    with _lock:
        return len(_times)


def reset() -> None:
    """Clear recorded latencies (used at demo start and by the test suite)."""
    with _lock:
        _times.clear()