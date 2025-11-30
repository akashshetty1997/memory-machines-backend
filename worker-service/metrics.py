"""
Memory Machines Backend - Metrics Module

Tracks basic per-instance runtime metrics.
"""

import time
from datetime import datetime, timezone
from typing import Optional

START_TIME = time.time()
REQUESTS_TOTAL = 0
LAST_REQUEST_AT: Optional[str] = None


def record_request(path: str) -> None:
    """
    Record an incoming request.
    Skips /health and /metrics so they don't pollute counters.
    """
    global REQUESTS_TOTAL, LAST_REQUEST_AT
    if path.startswith("/health") or path.startswith("/metrics"):
        return
    REQUESTS_TOTAL += 1
    LAST_REQUEST_AT = datetime.now(timezone.utc).isoformat()


def snapshot() -> dict:
    """
    Return a snapshot of current metrics as a dict.
    """
    uptime = int(time.time() - START_TIME)
    return {
        "service": "worker",
        "uptime_seconds": uptime,
        "requests_total": REQUESTS_TOTAL,
        "last_request_at": LAST_REQUEST_AT,
    }
