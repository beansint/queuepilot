"""In-process per-IP rate limiting + global daily cap (Slice E — D16).

No new runtime dependency (no ``slowapi``/Redis): a thread-safe, process-local fixed-window
counter per client IP, plus a process-global daily counter that resets at UTC midnight.
Fine for the single free-tier Render instance this app runs on (Redis-backed limiting is
deferred to horizontal scale — see ``05-DECISIONS-LOCKED.md`` D16).

Client IP: Render sits behind exactly one trusted proxy, which appends the real peer to
``X-Forwarded-For``. We therefore take the **rightmost** hop (the value our immediate proxy
observed) — NOT the leftmost, which is client-supplied and trivially spoofable to dodge the
per-IP limit. Falls back to ``request.client.host`` when the header is absent. (If ever run
behind N chained proxies, this would need a trusted-proxy count; one proxy = last hop.)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.config import get_settings

_WINDOW_SECONDS = 60.0
#: Bound memory: once a window dict exceeds this, expired entries are pruned. Prevents the
#: per-IP maps from growing without limit (one entry per distinct IP) and OOM-ing the
#: single free-tier instance.
_MAX_TRACKED_IPS = 10_000

_lock = threading.Lock()

# Per-IP fixed window for /analyze + /feedback: ip -> (window_start_epoch, count_in_window).
_ip_windows: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

# Separate per-IP window for /login (so login attempts don't consume the analyze budget
# and vice-versa) — the anti-brute-force guard.
_login_windows: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

# Global daily counter: (UTC day-number, count_today).
_daily_counter: tuple[int, int] = (0, 0)


def _client_ip(request: Request) -> str:
    """Client IP: the **rightmost** ``X-Forwarded-For`` hop (added by our trusted proxy),
    else the socket peer. The leftmost hop is client-supplied and spoofable, so it is not
    used for rate-limit keying."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last_hop = forwarded.split(",")[-1].strip()
        if last_hop:
            return last_hop
    return request.client.host if request.client else "unknown"


def _prune_expired(store: dict[str, tuple[float, int]], now: float) -> None:
    """Drop entries whose window has expired — only when *store* grows past the cap.
    Caller must hold ``_lock``. Bounds memory against a flood of distinct IPs."""
    if len(store) <= _MAX_TRACKED_IPS:
        return
    stale = [ip for ip, (start, _) in store.items() if now - start >= _WINDOW_SECONDS]
    for ip in stale:
        del store[ip]


def _touch_window(
    store: dict[str, tuple[float, int]], ip: str, limit_per_min: int, now: float
) -> bool:
    """Increment *ip*'s fixed window in *store*; return True if over ``limit_per_min``.
    Caller must hold ``_lock``."""
    window_start, count = store[ip]
    if now - window_start >= _WINDOW_SECONDS:
        window_start, count = now, 0
    count += 1
    store[ip] = (window_start, count)
    _prune_expired(store, now)
    return count > limit_per_min


def rate_limit(request: Request) -> None:
    """FastAPI dependency: enforce the per-IP rate limit AND the global daily cap.

    Both counter updates happen inside a single lock acquisition (one critical section per
    request). Raises ``429`` when either is exceeded. Counters are process-local and reset
    on restart; the per-IP window resets every 60s, the daily counter at UTC midnight.
    """
    global _daily_counter
    settings = get_settings()
    now = time.time()
    ip = _client_ip(request)
    today = int(now // 86400)
    with _lock:
        over_ip = _touch_window(_ip_windows, ip, settings.rate_limit_per_min, now)
        day, count = _daily_counter
        if day != today:
            day, count = today, 0
        count += 1
        _daily_counter = (day, count)
        over_cap = count > settings.daily_cap
    if over_ip:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    if over_cap:
        raise HTTPException(status_code=429, detail="daily demo quota reached, try again tomorrow")


def login_rate_limit(request: Request) -> None:
    """FastAPI dependency: stricter per-IP limit on ``POST /login`` to blunt brute-forcing
    the invite code. Raises ``429`` after ``LOGIN_ATTEMPTS_PER_MIN`` attempts/min per IP.
    Uses a counter separate from :func:`rate_limit` so login attempts and analyze traffic
    don't deplete each other."""
    settings = get_settings()
    now = time.time()
    ip = _client_ip(request)
    with _lock:
        over_limit = _touch_window(_login_windows, ip, settings.login_attempts_per_min, now)
    if over_limit:
        raise HTTPException(status_code=429, detail="too many login attempts")


def reset_state() -> None:
    """Reset all in-process counters. Test-only helper (isolates limiter state per test)."""
    global _ip_windows, _login_windows, _daily_counter
    with _lock:
        _ip_windows = defaultdict(lambda: (0.0, 0))
        _login_windows = defaultdict(lambda: (0.0, 0))
        _daily_counter = (0, 0)
