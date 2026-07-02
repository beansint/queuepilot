"""E10 — invite-code auth tests (offline; no network).

Covers:
  * sign/verify roundtrip and tamper -> None (app.auth, unit-level).
  * With auth configured (INVITE_CODE + SESSION_SECRET): POST /login wrong code -> 401,
    right code -> sets cookie + 200; POST /analyze without cookie -> 401, with a valid
    cookie -> not 401; GET /auth/status shapes.
  * With auth DISABLED (no INVITE_CODE): POST /analyze is reachable (no 401) — the
    graceful-degradation path that keeps offline tests / bare `docker run` working.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.auth as auth_mod
import app.main as main_mod
from app.auth import sign, verify
from app.config import Settings
from app.main import app
from app.ratelimit import reset_state
from app.schemas import AnalyzeResponse, SimilarTicket

_FAKE_RESPONSE = AnalyzeResponse(
    category="charge",
    queue="Billing",
    priority="high",
    confidence=0.82,
    similar_tickets=[
        SimilarTicket(score=0.95, queue="Billing", priority="high", type="charge", snippet="x"),
    ],
)


class _FakeGraphAnalyzer:
    def analyze(self, text: str, *, explain: bool = False) -> AnalyzeResponse:
        return _FAKE_RESPONSE


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    """Isolate the in-process rate-limit counters between tests."""
    reset_state()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.main.get_graph_analyzer", lambda: fake)
    return TestClient(app)


def _configure_auth(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> Settings:
    settings = Settings(invite_code="letmein", session_secret="s3cret", **overrides)  # type: ignore[arg-type]
    monkeypatch.setattr(auth_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(main_mod, "get_settings", lambda: settings)
    return settings


def _configure_no_auth(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> Settings:
    settings = Settings(invite_code=None, session_secret=None, **overrides)  # type: ignore[arg-type]
    monkeypatch.setattr(auth_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(main_mod, "get_settings", lambda: settings)
    return settings


# ---------------------------------------------------------------------------
# sign/verify (unit-level, no FastAPI)
# ---------------------------------------------------------------------------


def test_sign_verify_roundtrip() -> None:
    token = sign("authenticated", "secret-key")
    assert verify(token, "secret-key") == "authenticated"


def test_verify_wrong_secret_returns_none() -> None:
    token = sign("authenticated", "secret-key")
    assert verify(token, "different-secret") is None


def test_verify_tampered_token_returns_none() -> None:
    token = sign("authenticated", "secret-key")
    parts = token.split(".")
    # Flip the signature.
    parts[-1] = parts[-1][::-1] or "x"
    tampered = ".".join(parts)
    assert verify(tampered, "secret-key") is None


@pytest.mark.parametrize(
    "bad_token",
    ["", "not-a-token", "v1.onlytwo", "v2.a.b.c", "v1.a.b.c.d"],
)
def test_verify_malformed_token_returns_none(bad_token: str) -> None:
    assert verify(bad_token, "secret-key") is None


def test_verify_enforces_max_age() -> None:
    """With max_age set, a token older than the window is rejected; a fresh one still verifies.

    The signed ``iat`` is covered by the HMAC, so the age check cannot be forged. Using
    max_age=-1 forces even a just-issued token (age ~0) over the limit.
    """
    token = sign("authenticated", "secret-key")
    assert verify(token, "secret-key", max_age=3600) == "authenticated"
    assert verify(token, "secret-key", max_age=-1) is None


# ---------------------------------------------------------------------------
# Auth configured: /login, /analyze gating, /auth/status
# ---------------------------------------------------------------------------


def test_login_wrong_code_returns_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_auth(monkeypatch)
    resp = client.post("/login", json={"code": "wrong"})
    assert resp.status_code == 401


def test_login_right_code_sets_cookie_and_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_auth(monkeypatch)
    resp = client.post("/login", json={"code": "letmein"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert "qp_session" in resp.cookies


def test_login_non_ascii_code_returns_401_not_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-ASCII invite code must be a clean 401, not a 500 — hmac.compare_digest
    raises TypeError on non-ASCII str, so the handler compares bytes."""
    _configure_auth(monkeypatch)
    resp = client.post("/login", json={"code": "café🔑"})
    assert resp.status_code == 401


def test_analyze_without_cookie_returns_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_auth(monkeypatch)
    resp = client.post("/analyze", json={"text": "help me"})
    assert resp.status_code == 401


def test_analyze_with_valid_cookie_is_not_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_auth(monkeypatch)
    login_resp = client.post("/login", json={"code": "letmein"})
    assert login_resp.status_code == 200

    resp = client.post("/analyze", json={"text": "help me"})
    assert resp.status_code != 401
    assert resp.status_code == 200


def test_analyze_with_forged_cookie_returns_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_auth(monkeypatch)
    client.cookies.set("qp_session", "v1.Zm9y.123.deadbeef")
    resp = client.post("/analyze", json={"text": "help me"})
    assert resp.status_code == 401


def test_auth_status_shapes_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_auth(monkeypatch)

    resp = client.get("/auth/status")
    assert resp.json() == {"required": True, "authenticated": False}

    client.post("/login", json={"code": "letmein"})
    resp = client.get("/auth/status")
    assert resp.json() == {"required": True, "authenticated": True}


def test_logout_clears_cookie(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_auth(monkeypatch)
    client.post("/login", json={"code": "letmein"})
    assert client.get("/auth/status").json()["authenticated"] is True

    logout_resp = client.post("/logout")
    assert logout_resp.status_code == 200

    resp = client.post("/analyze", json={"text": "help me"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Auth disabled (graceful degradation — no INVITE_CODE/SESSION_SECRET)
# ---------------------------------------------------------------------------


def test_analyze_reachable_when_auth_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_no_auth(monkeypatch)
    resp = client.post("/analyze", json={"text": "help me"})
    assert resp.status_code == 200


def test_login_is_noop_when_auth_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_no_auth(monkeypatch)
    resp = client.post("/login", json={"code": "anything"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_auth_status_when_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_no_auth(monkeypatch)
    resp = client.get("/auth/status")
    assert resp.json() == {"required": False, "authenticated": False}
