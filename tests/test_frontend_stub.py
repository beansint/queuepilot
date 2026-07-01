"""C6 — serve-stub tests: app boots and serves a graceful placeholder without frontend/dist.

frontend/dist does not exist in CI/tests (frontend work is paused), so these tests exercise
exactly the path that always runs in this environment: the placeholder route registered at
`/` only (not a catch-all), so unmatched paths 404 and GET on POST-only routes 405s normally.
`/health`, `/analyze`, and `/docs` must keep working alongside it.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import _FRONTEND_INDEX, app

client = TestClient(app)


def test_frontend_dist_absent_in_test_env() -> None:
    """Sanity check: the placeholder path is the one actually exercised here."""
    assert not Path(_FRONTEND_INDEX).is_file()


def test_root_serves_placeholder_when_no_dist() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "QueuePilot API is running" in resp.text


def test_unknown_path_returns_404_when_no_dist() -> None:
    """Without a frontend build, unknown paths 404 normally (no catch-all placeholder)."""
    resp = client.get("/some-unknown-path")
    assert resp.status_code == 404


def test_health_still_works_alongside_placeholder() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_docs_still_works_alongside_placeholder() -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_analyze_route_not_shadowed_by_placeholder(monkeypatch: object) -> None:
    """/analyze (POST) is matched before the placeholder route."""
    # A POST to /analyze with invalid body should 422 (route matched), not 200 (placeholder).
    resp = client.post("/analyze", json={})
    assert resp.status_code == 422


def test_get_analyze_returns_405_not_placeholder() -> None:
    """GET /analyze must not be shadowed by the root-only placeholder route; 405 expected."""
    resp = client.get("/analyze")
    assert resp.status_code == 405
