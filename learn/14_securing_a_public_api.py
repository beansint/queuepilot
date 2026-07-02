"""learn/14_securing_a_public_api.py — E7: securing a public API.

Companion to docs/learn/14-securing-a-public-api.md. Run:

    uv run python learn/14_securing_a_public_api.py

Proves two things, fully offline (no network, no FastAPI TestClient) by importing and
calling the *real* app code:
  1. `app.auth.sign`/`verify` — a valid token verifies to its original value; a tampered
     token (flipped signature byte) is rejected (returns None).
  2. `app.ratelimit` — the real per-IP fixed-window counter allows exactly N requests then
     raises 429 on the (N+1)th; the real global daily-cap counter behaves the same way.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException  # noqa: E402

from app import ratelimit as ratelimit_mod  # noqa: E402
from app.auth import sign, verify  # noqa: E402
from app.config import Settings  # noqa: E402


def _fake_request(ip: str) -> MagicMock:
    """A minimal stand-in for fastapi.Request — only the attrs app.ratelimit reads."""
    req = MagicMock()
    req.headers = {"x-forwarded-for": ip}
    req.client = MagicMock(host=ip)
    return req


def main() -> None:
    print("== E7: securing a public API (invite cookie, rate limiting, daily cap) ==\n")

    # ------------------------------------------------------------------
    # Part 1: sign/verify — real app.auth, HMAC-SHA256 + constant-time compare.
    # ------------------------------------------------------------------
    print("-- Part 1: app.auth.sign / app.auth.verify --")
    secret = "demo-session-secret"
    token = sign("authenticated", secret)
    print(f"  sign('authenticated', secret) -> {token}")

    verified = verify(token, secret)
    print(f"  verify(token, secret)         -> {verified!r}")
    assert verified == "authenticated"
    print("  -> a valid token verifies back to its original signed value.\n")

    # Tamper with the signature (flip the last character).
    parts = token.split(".")
    parts[-1] = ("a" if parts[-1][-1] != "a" else "b") + parts[-1][1:]
    tampered = ".".join(parts)
    tampered_result = verify(tampered, secret)
    print(f"  tampered token: {tampered}")
    print(f"  verify(tampered, secret)      -> {tampered_result!r}")
    assert tampered_result is None
    print("  -> a tampered signature is rejected (None), never raises.\n")

    wrong_secret_result = verify(token, "not-the-real-secret")
    print(f"  verify(token, wrong_secret)   -> {wrong_secret_result!r}")
    assert wrong_secret_result is None
    print("  -> verifying with the wrong secret is also rejected.\n")

    # ------------------------------------------------------------------
    # Part 2: rate_limit — real app.ratelimit, per-IP window then global daily cap.
    # ------------------------------------------------------------------
    print("-- Part 2: app.ratelimit.rate_limit — per-IP window --")
    ratelimit_mod.reset_state()
    per_ip_limit = 3
    settings = Settings(rate_limit_per_min=per_ip_limit, daily_cap=1000)
    ratelimit_mod.get_settings = lambda: settings  # type: ignore[assignment]

    req = _fake_request("9.9.9.9")
    allowed = 0
    for i in range(per_ip_limit):
        ratelimit_mod.rate_limit(req)
        allowed += 1
        print(f"  request {i + 1}/{per_ip_limit} from 9.9.9.9 -> allowed")

    try:
        ratelimit_mod.rate_limit(req)
        raise AssertionError("expected the (N+1)th request to be rate-limited")
    except HTTPException as exc:
        over = per_ip_limit + 1
        print(f"  request {over}/{per_ip_limit} from 9.9.9.9 -> HTTPException(429): {exc.detail!r}")
        assert exc.status_code == 429

    assert allowed == per_ip_limit
    print(
        f"  -> exactly {per_ip_limit} requests/min allowed per client IP, "
        f"the {per_ip_limit + 1}th is 429.\n"
    )

    other_req = _fake_request("1.2.3.4")
    ratelimit_mod.rate_limit(other_req)
    print("  a different client IP (1.2.3.4) is unaffected -> allowed (its own window).\n")

    # ------------------------------------------------------------------
    # Part 3: rate_limit — global daily cap (shared across all client IPs).
    # ------------------------------------------------------------------
    print("-- Part 3: app.ratelimit.rate_limit — global daily cap --")
    ratelimit_mod.reset_state()
    daily_cap = 2
    settings = Settings(rate_limit_per_min=1000, daily_cap=daily_cap)
    ratelimit_mod.get_settings = lambda: settings  # type: ignore[assignment]

    for i in range(daily_cap):
        ratelimit_mod.rate_limit(_fake_request(f"10.0.0.{i}"))
        print(f"  request {i + 1}/{daily_cap} (from a distinct IP each time) -> allowed")

    try:
        ratelimit_mod.rate_limit(_fake_request("10.0.0.99"))
        raise AssertionError("expected the request beyond the daily cap to be rejected")
    except HTTPException as exc:
        over = daily_cap + 1
        print(f"  request {over}/{daily_cap} (yet another IP) -> HTTPException(429):")
        print(f"    {exc.detail!r}")
        assert exc.status_code == 429
        assert "daily" in str(exc.detail)

    ratelimit_mod.reset_state()

    print()
    print(
        "Conclusion: the same HMAC sign/verify and rate-limit code the FastAPI app wires "
        "into POST /analyze and POST /feedback works identically outside FastAPI — a "
        "tampered cookie never verifies, and the per-IP window plus the global daily cap "
        "are two independent 429 guards (one client hammering it vs. many clients draining "
        "the shared provider budget)."
    )


if __name__ == "__main__":
    main()
