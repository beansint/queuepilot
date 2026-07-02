"""D9/D14 — POST /feedback endpoint tests (offline; LangSmith client factory monkeypatched).

Covers:
  * 422 when score is not in {0, 1}.
  * 422 when run_id is missing.
  * Happy path with a mocked LangSmith client: create_feedback called once with the
    expected key/score/run_id/trace_id.
  * Correction path: create_examples called with the correction as outputs.
  * Graceful no-op: client factory returns None -> still 200 {"ok": true}, no exception.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _patch_feedback_client(monkeypatch: pytest.MonkeyPatch, fake_client: Mock | None) -> None:
    monkeypatch.setattr("app.main._get_feedback_client", lambda: fake_client)


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------


def test_feedback_invalid_score_returns_422(client: TestClient) -> None:
    """score not in {0, 1} triggers a 422 validation error."""
    resp = client.post("/feedback", json={"run_id": "run-123", "score": 2})
    assert resp.status_code == 422


def test_feedback_negative_score_returns_422(client: TestClient) -> None:
    """Negative score is also rejected."""
    resp = client.post("/feedback", json={"run_id": "run-123", "score": -1})
    assert resp.status_code == 422


def test_feedback_missing_run_id_returns_422(client: TestClient) -> None:
    """Missing run_id triggers a 422 validation error."""
    resp = client.post("/feedback", json={"score": 1})
    assert resp.status_code == 422


def test_feedback_empty_run_id_returns_422(client: TestClient) -> None:
    """Empty/whitespace-only run_id triggers a 422 validation error."""
    resp = client.post("/feedback", json={"run_id": "   ", "score": 1})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Happy path (mocked LangSmith client)
# ---------------------------------------------------------------------------


def test_feedback_happy_path_calls_create_feedback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured client gets create_feedback called with the expected args."""
    fake_client = Mock()
    _patch_feedback_client(monkeypatch, fake_client)

    resp = client.post("/feedback", json={"run_id": "run-123", "score": 1})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    fake_client.create_feedback.assert_called_once_with(
        "run-123",
        key="user_thumbs",
        score=1.0,
        comment=None,
        trace_id="run-123",
    )
    fake_client.create_examples.assert_not_called()


def test_feedback_happy_path_with_comment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """comment is forwarded to create_feedback."""
    fake_client = Mock()
    _patch_feedback_client(monkeypatch, fake_client)

    resp = client.post(
        "/feedback", json={"run_id": "run-456", "score": 0, "comment": "wrong queue"}
    )

    assert resp.status_code == 200
    fake_client.create_feedback.assert_called_once_with(
        "run-456",
        key="user_thumbs",
        score=0.0,
        comment="wrong queue",
        trace_id="run-456",
    )


# ---------------------------------------------------------------------------
# Correction flywheel
# ---------------------------------------------------------------------------


def test_feedback_correction_appends_example(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A correction body appends an example to the queuepilot-feedback dataset."""
    fake_client = Mock()
    fake_client.has_dataset.return_value = True
    _patch_feedback_client(monkeypatch, fake_client)

    correction = {"queue": "Billing", "priority": "high"}
    resp = client.post(
        "/feedback",
        json={"run_id": "run-789", "score": 0, "correction": correction},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    fake_client.create_examples.assert_called_once_with(
        dataset_name="queuepilot-feedback",
        examples=[{"inputs": {"run_id": "run-789"}, "outputs": correction}],
    )
    fake_client.create_dataset.assert_not_called()


def test_feedback_correction_creates_dataset_if_absent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the dataset doesn't exist yet, it is created before appending the example."""
    fake_client = Mock()
    fake_client.has_dataset.return_value = False
    _patch_feedback_client(monkeypatch, fake_client)

    resp = client.post(
        "/feedback",
        json={"run_id": "run-999", "score": 1, "correction": {"queue": "Technical Support"}},
    )

    assert resp.status_code == 200
    fake_client.create_dataset.assert_called_once_with("queuepilot-feedback")
    fake_client.create_examples.assert_called_once()


def test_feedback_correction_failure_still_returns_ok(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A flywheel failure (create_examples raises) still returns ok — best-effort."""
    fake_client = Mock()
    fake_client.has_dataset.return_value = True
    fake_client.create_examples.side_effect = RuntimeError("boom")
    _patch_feedback_client(monkeypatch, fake_client)

    resp = client.post(
        "/feedback",
        json={"run_id": "run-err", "score": 1, "correction": {"queue": "Billing"}},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Graceful no-op (LangSmith unconfigured)
# ---------------------------------------------------------------------------


def test_feedback_unconfigured_client_is_graceful_noop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the client factory returns None (LangSmith unconfigured), still 200 ok."""
    _patch_feedback_client(monkeypatch, None)

    resp = client.post("/feedback", json={"run_id": "run-noop", "score": 1})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_feedback_unexpected_error_is_swallowed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexpected create_feedback error is swallowed and still returns ok."""
    fake_client = Mock()
    fake_client.create_feedback.side_effect = RuntimeError("network down")
    _patch_feedback_client(monkeypatch, fake_client)

    resp = client.post("/feedback", json={"run_id": "run-boom", "score": 1})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
