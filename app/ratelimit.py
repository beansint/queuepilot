"""In-process per-IP rate limiting + global daily cap (Slice E — D16).

No new runtime dependency (no ``slowapi``/Redis): a thread-safe, process-local fixed-window
counter per client IP, plus a process-global daily counter that resets at UTC midnight.
Fine for the single free-tier Render instance this app runs on (Redis-backed limiting is
deferred to horizontal scale — see ``05-DECISIONS-LOCKED.md`` D16). Render sits behind a
proxy, so the client IP is taken from the first hop of ``X-Forwarded-For`` when present,
falling back to ``request.client.host``.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.config import get_settings

_WINDOW_SECONDS = 60.0

_lock = threading.Lock()

# Per-IP fixed window: ip -> (window_start_epoch, count_in_window).
_ip_windows: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

# Global daily counter: (UTC day-number, count_today).
_daily_counter: tuple[int, int] = (0, 0)


def _client_ip(request: Request) -> str:
    """Best-effort client IP: first hop of ``X-Forwarded-For``, else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    return request.client.host if request.client else "unknown"


def _check_per_ip(ip: str, limit_per_min: int, now: float) -> None:
    global _ip_windows
    with _lock:
        window_start, count = _ip_windows[ip]
        if now - window_start >= _WINDOW_SECONDS:
            window_start, count = now, 0
        count += 1
        _ip_windows[ip] = (window_start, count)
        over_limit = count > limit_per_min
    if over_limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded")


def _check_daily_cap(daily_cap: int, now: float) -> None:
    global _daily_counter
    today = int(now // 86400)
    with _lock:
        day, count = _daily_counter
        if day != today:
            day, count = today, 0
        count += 1
        _daily_counter = (day, count)
        over_cap = count > daily_cap
    if over_cap:
        raise HTTPException(
            status_code=429, detail="daily demo quota reached, try again tomorrow"
        )


def rate_limit(request: Request) -> None:
    """FastAPI dependency: enforce the per-IP rate limit, then the global daily cap.

    Raises ``429`` (per-IP limit) or ``429`` (daily cap) when exceeded. Both counters are
    process-local and reset on restart; the per-IP window resets every 60s, the daily
    counter resets at UTC midnight.
    """
    settings = get_settings()
    now = time.time()
    ip = _client_ip(request)
    _check_per_ip(ip, settings.rate_limit_per_min, now)
    _check_daily_cap(settings.daily_cap, now)


def reset_state() -> None:
    """Reset all in-process counters. Test-only helper (isolates limiter state per test)."""
    global _ip_windows, _daily_counter
    with _lock:
        _ip_windows = defaultdict(lambda: (0.0, 0))
        _daily_counter = (0, 0)
