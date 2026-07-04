"""D8 follow-up — GET /eval/snapshots + /eval/snapshots/{name} tests.

Reads the REAL committed snapshot at eval/snapshots/a0.5-groq.json (no mocking of file
contents) — only auth/rate-limit state is reset/patched, mirroring tests/test_feedback.py
and tests/test_graphql.py's auth-gating style.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.eval_api as eval_api_mod
from app.config import Settings
from app.main import app
from app.ratelimit import reset_state

REAL_SNAPSHOT_NAME = "a0.5-groq"


@pytest.fixture()
def client() -> TestClient:
    reset_state()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _unconfigured_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to auth-unconfigured (matches most tests' baseline) unless a test
    opts into a configured invite code."""
    monkeypatch.setattr(
        "app.auth.get_settings",
        lambda: Settings(invite_code=None, session_secret="s" * 32),
    )


def test_list_snapshots_reads_the_real_committed_file(client: TestClient) -> None:
    resp = client.get("/eval/snapshots")
    assert resp.status_code == 200
    body = resp.json()
    names = [s["name"] for s in body["snapshots"]]
    assert REAL_SNAPSHOT_NAME in names

    row = next(s for s in body["snapshots"] if s["name"] == REAL_SNAPSHOT_NAME)
    on_disk = json.loads((eval_api_mod.SNAPSHOTS_DIR / f"{REAL_SNAPSHOT_NAME}.json").read_text())
    assert row["n"] == on_disk["metrics"]["n"]
    assert row["queue_match"] == on_disk["metrics"]["queue_match"]
    assert row["ece"] == pytest.approx(on_disk["metrics"]["ece"])


def test_get_snapshot_returns_full_card(client: TestClient) -> None:
    resp = client.get(f"/eval/snapshots/{REAL_SNAPSHOT_NAME}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["n"] == 20
    assert body["metrics"]["config"] == {"alpha": 0.5, "chat": "groq"}
    assert len(body["metrics"]["reliability"]) == 4
    assert body["metrics"]["skipped_evaluators"] == ["reply_quality"]
    assert body["baseline"] is None


def test_get_snapshot_missing_name_is_404(client: TestClient) -> None:
    resp = client.get("/eval/snapshots/does-not-exist")
    assert resp.status_code == 404


def test_load_snapshot_json_rejects_path_traversal() -> None:
    # Exercised directly (not over HTTP): the httpx test client itself normalizes a
    # ``..``-bearing URL path before the request ever reaches routing, so this guard
    # can only be verified at the function level. ``Path(name).name`` strips any
    # directory components, so a traversal attempt resolves to a nonexistent
    # "<basename>.json" inside SNAPSHOTS_DIR and 404s rather than escaping it.
    with pytest.raises(Exception) as exc_info:
        eval_api_mod._load_snapshot_json("../../pyproject")
    assert getattr(exc_info.value, "status_code", None) == 404


def test_list_snapshots_empty_dir_returns_empty_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: "pytest.TempPathFactory"
) -> None:
    monkeypatch.setattr(eval_api_mod, "SNAPSHOTS_DIR", tmp_path)
    resp = client.get("/eval/snapshots")
    assert resp.status_code == 200
    assert resp.json() == {"snapshots": []}


def test_eval_snapshots_requires_auth_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.auth.get_settings",
        lambda: Settings(invite_code="letmein", session_secret="s" * 32),
    )
    resp = client.get("/eval/snapshots")
    assert resp.status_code == 401

    resp = client.get(f"/eval/snapshots/{REAL_SNAPSHOT_NAME}")
    assert resp.status_code == 401


def test_null_byte_name_returns_404_not_500(client: TestClient) -> None:
    """A name whose filesystem probe raises ValueError (embedded null) → clean 404."""
    resp = client.get("/eval/snapshots/bad%00name")
    assert resp.status_code == 404


def test_one_malformed_snapshot_does_not_break_the_listing(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single unparseable card must be skipped, not 404 the whole listing."""
    good = {"metrics": {"n": 3, "queue_match": 0.5}, "baseline": None}
    (tmp_path / "good.json").write_text(json.dumps(good))
    (tmp_path / "broken.json").write_text("{not valid json")  # half-written card
    monkeypatch.setattr(eval_api_mod, "SNAPSHOTS_DIR", tmp_path)

    resp = client.get("/eval/snapshots")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()["snapshots"]]
    assert names == ["good"]  # broken skipped, good survives
