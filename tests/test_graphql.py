"""F6 — GraphQL endpoint tests (offline; get_graph_analyzer / feedback client monkeypatched).

Covers the Slice F exit criteria:
  * analyze query returns the full envelope; field-selection returns ONLY requested fields.
  * REST parity: GraphQL analyze == REST POST /analyze for the same (faked) service result.
  * sentiment is a typed object; trace/debug are JSON; debug null unless explain: true.
  * auth gating (401 without a cookie when configured; open when unconfigured — parity with REST).
  * rate limit (429 past the per-IP cap) — same dependency as REST.
  * submitFeedback mutation → true (and best-effort no-op when LangSmith unconfigured).
  * invalid input / malformed query → a GraphQL `errors` array (HTTP 200), not 422/500.
  * health query is reachable; GraphiQL is served on GET.

No network: the LangGraph analyzer and the LangSmith client are faked, mirroring
tests/test_analyze_endpoint.py and tests/test_feedback.py.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import app.auth as auth_mod
import app.ratelimit as ratelimit_mod
from app.config import Settings
from app.main import app
from app.ratelimit import reset_state
from app.schemas import AnalyzeResponse, SimilarTicket

# ---------------------------------------------------------------------------
# Fakes (mirror test_analyze_endpoint.py)
# ---------------------------------------------------------------------------

_FAKE_RESPONSE = AnalyzeResponse(
    category="charge",
    queue="Billing",
    priority="high",
    confidence=0.82,
    similar_tickets=[
        SimilarTicket(score=0.95, queue="Billing", priority="high", type="charge", snippet="dup"),
        SimilarTicket(score=0.80, queue="Billing", priority="low", type="refund", snippet="amt"),
    ],
    sentiment={"frustration": 0.3, "negativity": 0.2},
    sla_risk=0.1,
    escalate=False,
    clarification=None,
    suggested_reply="Please check your billing statement.",
    trace={"enabled": False},
)

_FAKE_RESPONSE_WITH_DEBUG = _FAKE_RESPONSE.model_copy(
    update={
        "debug": {
            "nodes": [{"name": "classify", "rationale": "queue='Billing'"}],
            "retrieval": [],
            "confidence_breakdown": {"final": 0.82},
            "sla_breakdown": {"final": 0.1},
            "decision": "answer",
        }
    }
)


class _FakeGraphAnalyzer:
    def analyze(self, text: str, *, explain: bool = False) -> AnalyzeResponse:
        return _FAKE_RESPONSE_WITH_DEBUG if explain else _FAKE_RESPONSE


ANALYZE_FULL = """
query($t: String!, $e: Boolean) {
  analyze(text: $t, explain: $e) {
    category queue priority confidence
    similarTickets { score snippet queue priority type }
    sentiment { frustration negativity }
    slaRisk escalate clarification suggestedReply trace debug
  }
}
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_limiter() -> None:
    """Isolate the in-process rate-limit counters between tests."""
    reset_state()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with the analyzer faked (no network). Auth is open (no INVITE_CODE)."""
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.graphql.schema.get_graph_analyzer", lambda: fake)
    return TestClient(app)


def _gql(
    client: TestClient, query: str, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    resp = client.post("/graphql", json={"query": query, "variables": variables or {}})
    return {"status": resp.status_code, "body": resp.json()}


def _configure_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(invite_code="letmein", session_secret="s3cret")
    monkeypatch.setattr(auth_mod, "get_settings", lambda: settings)


# ---------------------------------------------------------------------------
# Query: analyze (happy path + field selection)
# ---------------------------------------------------------------------------


def test_health_query(client: TestClient) -> None:
    out = _gql(client, "{ health { status app environment } }")
    assert out["status"] == 200
    assert out["body"]["data"]["health"]["status"] == "ok"


def test_analyze_full_envelope(client: TestClient) -> None:
    out = _gql(client, ANALYZE_FULL, {"t": "charged twice", "e": False})
    data = out["body"]["data"]["analyze"]
    assert data["category"] == "charge"
    assert data["queue"] == "Billing"
    assert data["confidence"] == pytest.approx(0.82)
    assert len(data["similarTickets"]) == 2
    assert data["suggestedReply"] == "Please check your billing statement."


def test_field_selection_returns_only_requested_fields(client: TestClient) -> None:
    out = _gql(client, '{ analyze(text: "x") { queue confidence } }')
    data = out["body"]["data"]["analyze"]
    # ONLY the two requested fields are present — GraphQL's signature property.
    assert set(data.keys()) == {"queue", "confidence"}


def test_sentiment_is_typed_object(client: TestClient) -> None:
    out = _gql(client, '{ analyze(text: "x") { sentiment { frustration negativity } } }')
    assert out["body"]["data"]["analyze"]["sentiment"] == {
        "frustration": pytest.approx(0.3),
        "negativity": pytest.approx(0.2),
    }


def test_trace_is_json_scalar(client: TestClient) -> None:
    out = _gql(client, '{ analyze(text: "x") { trace } }')
    assert out["body"]["data"]["analyze"]["trace"] == {"enabled": False}


def test_debug_null_unless_explain(client: TestClient) -> None:
    out = _gql(client, ANALYZE_FULL, {"t": "x", "e": False})
    assert out["body"]["data"]["analyze"]["debug"] is None


def test_explain_populates_debug(client: TestClient) -> None:
    out = _gql(client, ANALYZE_FULL, {"t": "x", "e": True})
    debug = out["body"]["data"]["analyze"]["debug"]
    assert debug is not None
    assert debug["decision"] == "answer"


# ---------------------------------------------------------------------------
# REST parity
# ---------------------------------------------------------------------------


def test_graphql_matches_rest_analyze(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same (faked) service result → GraphQL analyze == REST POST /analyze."""
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.graphql.schema.get_graph_analyzer", lambda: fake)
    monkeypatch.setattr("app.main.get_graph_analyzer", lambda: fake)
    tc = TestClient(app)

    rest = tc.post("/analyze", json={"text": "charged twice"}).json()
    gql = _gql(tc, ANALYZE_FULL, {"t": "charged twice", "e": False})["body"]["data"]["analyze"]

    assert gql["category"] == rest["category"]
    assert gql["queue"] == rest["queue"]
    assert gql["priority"] == rest["priority"]
    assert gql["confidence"] == pytest.approx(rest["confidence"])
    assert gql["slaRisk"] == pytest.approx(rest["sla_risk"])  # camelCase parity
    assert gql["escalate"] == rest["escalate"]
    assert gql["suggestedReply"] == rest["suggested_reply"]
    assert len(gql["similarTickets"]) == len(rest["similar_tickets"])


# ---------------------------------------------------------------------------
# Errors (GraphQL errors array, HTTP 200 — not 422/500)
# ---------------------------------------------------------------------------


def test_empty_text_returns_graphql_error(client: TestClient) -> None:
    out = _gql(client, ANALYZE_FULL, {"t": "   ", "e": False})
    assert out["status"] == 200
    assert out["body"].get("errors")
    assert out["body"]["data"] is None


def test_malformed_query_returns_errors(client: TestClient) -> None:
    out = _gql(client, "{ analyze(text: ) { queue } }")  # syntactically invalid
    assert out["body"].get("errors")


# ---------------------------------------------------------------------------
# Mutation: submitFeedback
# ---------------------------------------------------------------------------

_FEEDBACK_MUTATION = "mutation($i: FeedbackInput!) { submitFeedback(input: $i) }"


def test_submit_feedback_true(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.graphql.schema._cached_feedback_client", lambda: Mock())
    out = _gql(client, _FEEDBACK_MUTATION, {"i": {"runId": "run-1", "score": 1}})
    assert out["body"]["data"]["submitFeedback"] is True


def test_submit_feedback_noop_when_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.graphql.schema._cached_feedback_client", lambda: None)
    out = _gql(client, _FEEDBACK_MUTATION, {"i": {"runId": "run-1", "score": 0}})
    assert out["body"]["data"]["submitFeedback"] is True


def test_submit_feedback_invalid_score_errors(client: TestClient) -> None:
    out = _gql(client, _FEEDBACK_MUTATION, {"i": {"runId": "run-1", "score": 2}})
    assert out["body"].get("errors")


# ---------------------------------------------------------------------------
# GraphiQL + gating
# ---------------------------------------------------------------------------


def test_graphiql_served_on_get(client: TestClient) -> None:
    resp = client.get("/graphql", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert "graphiql" in resp.text.lower()


def test_auth_gating_401_without_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.graphql.schema.get_graph_analyzer", lambda: fake)
    _configure_auth(monkeypatch)
    tc = TestClient(app)
    resp = tc.post("/graphql", json={"query": "{ health { status } }"})
    assert resp.status_code == 401


def test_auth_gating_ok_with_valid_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.graphql.schema.get_graph_analyzer", lambda: fake)
    _configure_auth(monkeypatch)
    cookie = auth_mod.issue_cookie_value()
    tc = TestClient(app, cookies={auth_mod.COOKIE_NAME: cookie})
    resp = tc.post("/graphql", json={"query": "{ health { status } }"})
    assert resp.status_code == 200
    assert resp.json()["data"]["health"]["status"] == "ok"


def test_rate_limit_429(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeGraphAnalyzer()
    monkeypatch.setattr("app.graphql.schema.get_graph_analyzer", lambda: fake)
    low = Settings(rate_limit_per_min=2)
    monkeypatch.setattr(ratelimit_mod, "get_settings", lambda: low)
    tc = TestClient(app)
    q = {"query": "{ health { status } }"}
    assert tc.post("/graphql", json=q).status_code == 200
    assert tc.post("/graphql", json=q).status_code == 200
    assert tc.post("/graphql", json=q).status_code == 429  # 3rd exceeds per-IP cap of 2
