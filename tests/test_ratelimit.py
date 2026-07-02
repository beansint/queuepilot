"""E10 — rate limit + daily cap tests (offline; no network).

Covers:
  * Per-IP fixed-window limit: with a low RATE_LIMIT_PER_MIN, N requests are allowed and
    the (N+1)th returns 429.
  * Daily cap: with a low DAILY_CAP, requests beyond the cap return 429, even across
    different client IPs (the daily counter is global, not per-IP).
  * Limiter state is reset between tests via the `_reset_limiter` autouse fixture so
    counters don't leak across test functions.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.auth as auth_mod
import app.main as main_mod
import app.ratelimit as ratelimit_mod
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
    reset_state()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.main.get_graph_analyzer", lambda: fake)
    return TestClient(app)


def _configure_limits(
    monkeypatch: pytest.MonkeyPatch, *, rate_limit_per_min: int, daily_cap: int
) -> Settings:
    settings = Settings(
        invite_code=None,
        session_secret=None,
        rate_limit_per_min=rate_limit_per_min,
        daily_cap=daily_cap,
    )
    monkeypatch.setattr(ratelimit_mod, "get_settings", lambda: settings)
    return settings


def test_per_ip_limit_allows_n_then_429(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With RATE_LIMIT_PER_MIN=3, the first 3 requests succeed and the 4th is 429."""
    _configure_limits(monkeypatch, rate_limit_per_min=3, daily_cap=1000)

    statuses = [client.post("/analyze", json={"text": "help me"}).status_code for _ in range(3)]
    assert statuses == [200, 200, 200]

    over_limit = client.post("/analyze", json={"text": "help me"})
    assert over_limit.status_code == 429
    assert "rate limit" in over_limit.json()["detail"]


def test_per_ip_limit_is_independent_per_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A different client IP gets its own window (keyed on the X-Forwarded-For client IP)."""
    _configure_limits(monkeypatch, rate_limit_per_min=1, daily_cap=1000)

    first = client.post(
        "/analyze", json={"text": "help me"}, headers={"X-Forwarded-For": "1.1.1.1"}
    )
    assert first.status_code == 200

    # Same IP again -> over its own limit.
    second = client.post(
        "/analyze", json={"text": "help me"}, headers={"X-Forwarded-For": "1.1.1.1"}
    )
    assert second.status_code == 429

    # A different IP has its own fresh window.
    third = client.post(
        "/analyze", json={"text": "help me"}, headers={"X-Forwarded-For": "2.2.2.2"}
    )
    assert third.status_code == 200


def test_daily_cap_returns_429_once_exceeded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With DAILY_CAP=2, the 3rd request of the day (any IP) returns 429."""
    _configure_limits(monkeypatch, rate_limit_per_min=1000, daily_cap=2)

    first = client.post("/analyze", json={"text": "a"}, headers={"X-Forwarded-For": "3.3.3.3"})
    second = client.post("/analyze", json={"text": "b"}, headers={"X-Forwarded-For": "4.4.4.4"})
    assert first.status_code == 200
    assert second.status_code == 200

    third = client.post("/analyze", json={"text": "c"}, headers={"X-Forwarded-For": "5.5.5.5"})
    assert third.status_code == 429
    assert "daily" in third.json()["detail"]


def test_health_is_never_rate_limited(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /health has no rate_limit dependency — many calls never 429."""
    _configure_limits(monkeypatch, rate_limit_per_min=1, daily_cap=1)
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_xff_uses_rightmost_hop_not_spoofable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Varying the client-controlled LEFT X-Forwarded-For hop must NOT create fresh buckets.

    Render appends the real peer as the rightmost hop, so keying on the rightmost hop means
    a spoofed left value can't dodge the per-IP limit.
    """
    _configure_limits(monkeypatch, rate_limit_per_min=1, daily_cap=1000)

    first = client.post(
        "/analyze", json={"text": "a"}, headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}
    )
    assert first.status_code == 200

    # Different spoofed left hop, SAME real (rightmost) hop -> same bucket -> 429.
    second = client.post(
        "/analyze", json={"text": "b"}, headers={"X-Forwarded-For": "8.8.8.8, 1.1.1.1"}
    )
    assert second.status_code == 429


def test_login_is_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /login is throttled per-IP (anti-brute-force): with a low limit, wrong-code
    attempts return 401 up to the cap, then 429."""
    settings = Settings(
        invite_code="letmein",
        session_secret="s3cret",
        login_attempts_per_min=3,
    )
    for mod in (auth_mod, main_mod, ratelimit_mod):
        monkeypatch.setattr(mod, "get_settings", lambda: settings)

    statuses = [client.post("/login", json={"code": "wrong"}).status_code for _ in range(3)]
    assert statuses == [401, 401, 401]

    throttled = client.post("/login", json={"code": "wrong"})
    assert throttled.status_code == 429
    assert "login" in throttled.json()["detail"]
