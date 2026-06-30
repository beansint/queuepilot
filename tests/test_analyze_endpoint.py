"""B10/B11 — POST /analyze endpoint tests (no network; get_graph_analyzer is monkeypatched).

Covers:
  * POST /analyze with valid text returns 200 + correct envelope shape.
  * POST /analyze with oversized text returns 422 (FastAPI validation).
  * POST /analyze with empty text returns 422.
  * The response JSON includes all expected Slice-B keys (previously reserved fields
    may be non-null now that GraphAnalyzer populates them).
  * The endpoint wires to get_graph_analyzer(), not get_analyzer().

NOTE: The original A8 tests that verified reserved fields are null are updated here —
in Slice B those fields are populated by the graph, so the fixture now returns a
Slice-B style response (with sentiment/escalate/etc filled).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AnalyzeResponse, SimilarTicket

# ---------------------------------------------------------------------------
# Known AnalyzeResponse returned by the fake GraphAnalyzer
# ---------------------------------------------------------------------------

_FAKE_RESPONSE = AnalyzeResponse(
    category="charge",
    queue="Billing",
    priority="high",
    confidence=0.82,
    similar_tickets=[
        SimilarTicket(score=0.95, queue="Billing", priority="high", type="charge",
                      snippet="Charged twice"),
        SimilarTicket(score=0.80, queue="Billing", priority="low",  type="refund",
                      snippet="Wrong amount"),
    ],
    # Slice-B fields — populated by GraphAnalyzer in the wild
    sentiment={"frustration": 0.3, "negativity": 0.2},
    sla_risk=0.1,
    escalate=False,
    clarification=None,
    suggested_reply="Please check your billing statement.",
)


class _FakeGraphAnalyzer:
    """Minimal GraphAnalyzer stub — always returns _FAKE_RESPONSE."""

    def analyze(self, text: str) -> AnalyzeResponse:
        return _FAKE_RESPONSE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with get_graph_analyzer patched to avoid network calls."""
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.main.get_graph_analyzer", lambda: fake)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_analyze_returns_200(client: TestClient) -> None:
    """Valid request returns HTTP 200."""
    resp = client.post("/analyze", json={"text": "printer is offline"})
    assert resp.status_code == 200


def test_analyze_response_has_category(client: TestClient) -> None:
    """Response JSON contains the category field."""
    resp = client.post("/analyze", json={"text": "billing problem"})
    body = resp.json()
    assert body["category"] == "charge"


def test_analyze_response_has_queue(client: TestClient) -> None:
    """Response JSON contains the queue field."""
    resp = client.post("/analyze", json={"text": "billing problem"})
    assert resp.json()["queue"] == "Billing"


def test_analyze_response_has_priority(client: TestClient) -> None:
    """Response JSON contains the priority field."""
    resp = client.post("/analyze", json={"text": "billing problem"})
    assert resp.json()["priority"] == "high"


def test_analyze_response_confidence_in_range(client: TestClient) -> None:
    """confidence is a float in [0.0, 1.0]."""
    body = client.post("/analyze", json={"text": "billing problem"}).json()
    conf = body["confidence"]
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0


def test_analyze_response_similar_tickets_present(client: TestClient) -> None:
    """similar_tickets is a list with at least one entry."""
    body = client.post("/analyze", json={"text": "billing problem"}).json()
    tickets = body["similar_tickets"]
    assert isinstance(tickets, list)
    assert len(tickets) == 2


def test_analyze_response_similar_ticket_shape(client: TestClient) -> None:
    """Each similar_ticket has score and snippet."""
    body = client.post("/analyze", json={"text": "billing problem"}).json()
    ticket = body["similar_tickets"][0]
    assert "score" in ticket
    assert "snippet" in ticket


def test_analyze_slice_b_fields_present(client: TestClient) -> None:
    """Slice-B fields are populated (non-null) now that GraphAnalyzer is wired in."""
    body = client.post("/analyze", json={"text": "billing problem"}).json()
    # Slice-B fields are now populated by GraphAnalyzer
    assert body["sentiment"] is not None, "sentiment should be populated in Slice B"
    assert body["sla_risk"] is not None, "sla_risk should be populated in Slice B"
    assert body["escalate"] is not None, "escalate should be populated in Slice B"
    assert body["suggested_reply"] is not None, "suggested_reply should be populated in Slice B"
    # trace is still null until Slice C
    assert body["trace"] is None, "trace must remain null until Slice C"


def test_analyze_with_metadata(client: TestClient) -> None:
    """Optional metadata field does not break the endpoint."""
    resp = client.post(
        "/analyze",
        json={"text": "vpn not working", "metadata": {"channel": "email"}},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------


def test_analyze_oversized_text_returns_422(client: TestClient) -> None:
    """Text exceeding MAX_INPUT_CHARS (8000) triggers a 422 validation error."""
    resp = client.post("/analyze", json={"text": "x" * 8001})
    assert resp.status_code == 422


def test_analyze_empty_text_returns_422(client: TestClient) -> None:
    """Empty / whitespace-only text triggers a 422 validation error."""
    resp = client.post("/analyze", json={"text": "   "})
    assert resp.status_code == 422


def test_analyze_missing_text_returns_422(client: TestClient) -> None:
    """Missing text field triggers a 422 validation error."""
    resp = client.post("/analyze", json={})
    assert resp.status_code == 422


def test_analyze_exactly_at_limit_is_accepted(client: TestClient) -> None:
    """Text of exactly MAX_INPUT_CHARS characters is accepted (boundary value)."""
    resp = client.post("/analyze", json={"text": "x" * 8000})
    assert resp.status_code == 200
