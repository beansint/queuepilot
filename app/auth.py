"""Invite-code auth: signed HTTP-only session cookie (Slice E — D16).

No new runtime dependency: cookie signing uses stdlib ``hmac`` + ``hashlib`` + ``base64``
only (constant-time compare via ``hmac.compare_digest``). Mirrors how tracing degrades to
a no-op elsewhere in the app (``app.analyze.graph_analyzer``, ``app.feedback``): when
``INVITE_CODE`` / ``SESSION_SECRET`` are unset, :func:`auth_required` is ``False`` and every
gated route stays open — this keeps offline tests and a bare ``docker run`` (no env)
working exactly as before Slice E.

Cookie value format: ``v1.<b64(value)>.<iat>.<sig>`` — a signature-based token (no hard
expiry; ``iat`` is carried for future use, e.g. a rolling max-age policy). This deviates
slightly from the shorthand ``v1.<iat>.<sig>`` sketch in the task brief: the value is
base64-encoded into the payload so :func:`verify` can hand back the original signed value
(needed for a generic sign/verify pair, not just a boolean check) while still being fully
covered by the HMAC — the safer reading of an otherwise-ambiguous format.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from app.config import get_settings

COOKIE_NAME = "qp_session"

_TOKEN_VERSION = "v1"
_SESSION_VALUE = "authenticated"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign(value: str, secret: str) -> str:
    """Sign ``value`` with HMAC-SHA256 keyed by ``secret``.

    Returns a token of the form ``v1.<b64(value)>.<iat>.<sig>``. ``iat`` (issued-at, unix
    seconds) is included in the signed payload for future use (e.g. expiry policies) but is
    not itself enforced here — verification is purely signature-based.
    """
    b64_value = _b64encode(value.encode("utf-8"))
    iat = str(int(time.time()))
    payload = f"{b64_value}.{iat}"
    digest = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    sig = _b64encode(digest)
    return f"{_TOKEN_VERSION}.{payload}.{sig}"


def verify(token: str, secret: str) -> str | None:
    """Verify a token produced by :func:`sign`; return the original value or ``None``.

    Returns ``None`` on any tamper, malformed token, or unexpected error — never raises.
    Uses ``hmac.compare_digest`` for a constant-time signature comparison.
    """
    try:
        parts = token.split(".")
        if len(parts) != 4:
            return None
        version, b64_value, iat, sig = parts
        if version != _TOKEN_VERSION:
            return None
        payload = f"{b64_value}.{iat}"
        expected_sig = _b64encode(
            hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return _b64decode(b64_value).decode("utf-8")
    except Exception:
        return None


def auth_required() -> bool:
    """Whether invite-code auth is active.

    Auth is disabled (open) unless both ``INVITE_CODE`` and ``SESSION_SECRET`` are set —
    this is the graceful-degradation switch that keeps unconfigured deployments (local dev
    without a ``.env``, offline tests) working without a 401 wall.
    """
    settings = get_settings()
    return bool(settings.invite_code and settings.session_secret)


def issue_cookie_value() -> str:
    """Build the signed cookie value for a successful login.

    Requires :func:`auth_required` to be ``True`` (callers check this first); raises
    ``RuntimeError`` otherwise since ``session_secret`` would be ``None``.
    """
    settings = get_settings()
    if not settings.session_secret:
        raise RuntimeError("issue_cookie_value called without SESSION_SECRET configured")
    return sign(_SESSION_VALUE, settings.session_secret)


def _cookie_is_valid(token: str | None) -> bool:
    settings = get_settings()
    if not token or not settings.session_secret:
        return False
    return verify(token, settings.session_secret) == _SESSION_VALUE


def is_request_authenticated(request: Request) -> bool:
    """Whether ``request`` carries a valid, currently-verifiable session cookie."""
    return _cookie_is_valid(request.cookies.get(COOKIE_NAME))


def require_auth(request: Request) -> None:
    """FastAPI dependency gating a route behind a valid invite-code session cookie.

    A pure no-op (allows the request through) when :func:`auth_required` is ``False`` —
    the graceful-degradation path. Otherwise raises ``401`` unless ``request`` carries a
    cookie that verifies against ``SESSION_SECRET``.
    """
    if not auth_required():
        return
    if not is_request_authenticated(request):
        raise HTTPException(status_code=401, detail="invite code required")
