"""B10/B11 — offline unit tests for GraphAnalyzer (no network, no LLM calls).

Covers:
  * Answer-path: graph returns a full TicketState → AnalyzeResponse mapping is correct
    for all fields including the now-populated Slice-B fields.
  * Clarify/escalate path: verify clarification / escalate / suggested_reply mapping.
  * Fallback path: graph.invoke raises → GraphAnalyzer falls back to Slice A Analyzer
    and still returns a valid AnalyzeResponse.
  * Confidence clamping: graph returns out-of-range confidence → clamped to [0, 1].
  * similar_tickets ordering: mapped list preserves the neighbor order (descending score).
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.analyze.graph_analyzer import GraphAnalyzer, _ensure_langsmith_env
from app.config import Settings
from app.retrieval.pinecone_store import Neighbor
from app.schemas import AnalyzeResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_neighbors(n: int = 3) -> list[Neighbor]:
    """Return *n* Neighbor objects in descending score order."""
    return [
        Neighbor(
            score=round(0.9 - i * 0.1, 1),
            queue="IT Support",
            priority="high",
            type="Incident",
            snippet=f"snippet {i}",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Answer-path
# ---------------------------------------------------------------------------


def test_analyze_answer_path_fields() -> None:
    """Full TicketState with decision='answer' → all fields mapped correctly."""
    neighbors = _make_neighbors(3)

    canned_state: dict[str, Any] = {
        "text": "my printer is offline",
        "neighbors": neighbors,
        "category": "Incident",
        "queue": "IT Support",
        "priority": "high",
        "sentiment": {"frustration": 0.2, "negativity": 0.1},
        "missing_info": [],
        "sla_risk": 0.15,
        "confidence": 0.82,
        "decision": "answer",
        "escalate": False,
        "clarification": [],
        "suggested_reply": "Please restart the print spooler service.",
    }

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = canned_state

    result = GraphAnalyzer(graph=fake_graph).analyze("my printer is offline")

    assert isinstance(result, AnalyzeResponse)
    assert result.category == "Incident"
    assert result.queue == "IT Support"
    assert result.priority == "high"
    assert result.confidence == pytest.approx(0.82)
    assert 0.0 <= result.confidence <= 1.0
    assert result.sentiment == {"frustration": 0.2, "negativity": 0.1}
    assert result.sla_risk == pytest.approx(0.15)
    assert result.escalate is False
    # clarification is an empty list → normalised to None
    assert result.clarification is None
    assert result.suggested_reply == "Please restart the print spooler service."
    # No LANGSMITH_API_KEY in the test environment → tracing off → minimal disabled shape.
    assert result.trace == {"enabled": False}


def test_analyze_answer_path_similar_tickets_order() -> None:
    """similar_tickets are in descending score order matching neighbor input order."""
    neighbors = _make_neighbors(3)
    canned_state: dict[str, Any] = {
        "text": "test",
        "neighbors": neighbors,
        "category": None,
        "queue": None,
        "priority": None,
        "sentiment": None,
        "missing_info": [],
        "sla_risk": None,
        "confidence": 0.5,
        "decision": "answer",
        "escalate": False,
        "clarification": [],
        "suggested_reply": None,
    }

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = canned_state

    result = GraphAnalyzer(graph=fake_graph).analyze("test")

    assert len(result.similar_tickets) == 3
    scores = [t.score for t in result.similar_tickets]
    assert scores == sorted(scores, reverse=True), "similar_tickets must be descending by score"
    assert result.similar_tickets[0].score == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Clarify-path
# ---------------------------------------------------------------------------


def test_analyze_clarify_path() -> None:
    """TicketState with decision='clarify' → clarification populated, escalate=False."""
    neighbors = _make_neighbors(2)
    canned_state: dict[str, Any] = {
        "text": "something is broken",
        "neighbors": neighbors,
        "category": "Incident",
        "queue": "IT Support",
        "priority": "medium",
        "sentiment": {"frustration": 0.5, "negativity": 0.4},
        "missing_info": ["no error message", "no steps to reproduce"],
        "sla_risk": 0.3,
        "confidence": 0.55,
        "decision": "clarify",
        "escalate": False,
        "clarification": [
            "Could you share the exact error message you see?",
            "What steps did you follow before the issue occurred?",
        ],
        "suggested_reply": None,
    }

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = canned_state

    result = GraphAnalyzer(graph=fake_graph).analyze("something is broken")

    assert result.escalate is False
    assert isinstance(result.clarification, list)
    assert len(result.clarification) == 2
    assert "error message" in result.clarification[0]
    assert result.suggested_reply is None


# ---------------------------------------------------------------------------
# Escalate-path
# ---------------------------------------------------------------------------


def test_analyze_escalate_path() -> None:
    """TicketState with decision='escalate' → escalate=True, clarification=None."""
    canned_state: dict[str, Any] = {
        "text": "urgent server down",
        "neighbors": _make_neighbors(1),
        "category": None,
        "queue": None,
        "priority": "critical",
        "sentiment": {"frustration": 0.9, "negativity": 0.8},
        "missing_info": [],
        "sla_risk": 0.95,
        "confidence": 0.2,
        "decision": "escalate",
        "escalate": True,
        # clarification key absent (escalate branch skips the clarify node)
        "suggested_reply": None,
    }

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = canned_state

    result = GraphAnalyzer(graph=fake_graph).analyze("urgent server down")

    assert result.escalate is True
    assert result.clarification is None
    assert result.suggested_reply is None


# ---------------------------------------------------------------------------
# Fallback-to-baseline path
# ---------------------------------------------------------------------------


def test_analyze_fallback_on_graph_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When graph.invoke raises, GraphAnalyzer falls back to Slice A Analyzer."""
    fallback_response = AnalyzeResponse(
        category="fallback-category",
        queue="fallback-queue",
        priority="low",
        confidence=0.3,
        similar_tickets=[],
    )

    # Fake Analyzer.from_settings() so the fallback doesn't hit the network.
    class _FakeAnalyzer:
        def analyze(self, text: str) -> AnalyzeResponse:
            return fallback_response

    monkeypatch.setattr(
        "app.analyze.graph_analyzer.Analyzer.from_settings",
        staticmethod(lambda: _FakeAnalyzer()),
    )

    # Graph whose invoke always raises.
    fake_graph = MagicMock()
    fake_graph.invoke.side_effect = RuntimeError("Groq is down")

    result = GraphAnalyzer(graph=fake_graph).analyze("cannot connect to vpn")

    # Must return a valid AnalyzeResponse (not re-raise).
    assert isinstance(result, AnalyzeResponse)
    assert result.category == "fallback-category"
    assert result.queue == "fallback-queue"
    assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Confidence clamping
# ---------------------------------------------------------------------------


def test_analyze_confidence_clamped_above_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Out-of-range confidence > 1.0 from graph is clamped to 1.0."""
    canned_state: dict[str, Any] = {
        "text": "test",
        "neighbors": [],
        "confidence": 1.5,  # bug in scoring node
        "decision": "answer",
        "escalate": False,
    }

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = canned_state

    result = GraphAnalyzer(graph=fake_graph).analyze("test")
    assert result.confidence <= 1.0


# ---------------------------------------------------------------------------
# C4 — --explain accumulator
# ---------------------------------------------------------------------------


def _canned_state_with_debug() -> dict[str, Any]:
    neighbors = _make_neighbors(2)
    return {
        "text": "printer offline",
        "neighbors": neighbors,
        "category": "Incident",
        "queue": "IT Support",
        "priority": "high",
        "sentiment": {"frustration": 0.2, "negativity": 0.1},
        "missing_info": [],
        "sla_risk": 0.15,
        "confidence": 0.82,
        "decision": "answer",
        "escalate": False,
        "clarification": [],
        "suggested_reply": "Please restart the print spooler service.",
        "reasoning": {
            "classify": "LLM classified queue='IT Support'.",
            "score": "confidence=0.820 sla_risk=0.150.",
        },
        "confidence_breakdown": {"final": 0.82, "agreement": 1.0},
        "sla_breakdown": {"final": 0.15, "priority_weight": 1.0},
    }


def test_analyze_explain_true_populates_debug() -> None:
    """analyze(explain=True) assembles debug from the in-app reasoning/breakdown accumulator."""
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = _canned_state_with_debug()

    result = GraphAnalyzer(graph=fake_graph).analyze("printer offline", explain=True)

    assert result.debug is not None
    assert result.debug["decision"] == "answer"
    assert result.debug["confidence_breakdown"] == {"final": 0.82, "agreement": 1.0}
    assert result.debug["sla_breakdown"] == {"final": 0.15, "priority_weight": 1.0}
    node_names = {n["name"] for n in result.debug["nodes"]}
    assert node_names == {"classify", "score"}
    assert len(result.debug["retrieval"]) == 2
    assert "score" in result.debug["retrieval"][0]


def test_analyze_explain_false_leaves_debug_none() -> None:
    """analyze(explain=False) (the default) never populates debug."""
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = _canned_state_with_debug()

    result = GraphAnalyzer(graph=fake_graph).analyze("printer offline")

    assert result.debug is None


def test_analyze_confidence_clamped_below_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Out-of-range confidence < 0.0 from graph is clamped to 0.0."""
    canned_state: dict[str, Any] = {
        "text": "test",
        "neighbors": [],
        "confidence": -0.5,  # bug in scoring node
        "decision": "answer",
        "escalate": False,
    }

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = canned_state

    result = GraphAnalyzer(graph=fake_graph).analyze("test")
    assert result.confidence >= 0.0


# ---------------------------------------------------------------------------
# Fallback trace shape (documented {"enabled": False}, not None)
# ---------------------------------------------------------------------------


def test_analyze_fallback_trace_shape_documented(monkeypatch: pytest.MonkeyPatch) -> None:
    """On graph failure, the fallback response's trace/debug match the documented shape.

    The Slice A ``Analyzer`` doesn't populate ``trace``/``debug`` at all (they default to
    ``None`` on ``AnalyzeResponse``); the fallback path must still return the documented
    ``trace={"enabled": False}`` / ``debug=None`` shape rather than leaking a bare ``None``.
    """
    fallback_response = AnalyzeResponse(
        category="fallback-category",
        queue="fallback-queue",
        priority="low",
        confidence=0.3,
        similar_tickets=[],
    )
    assert fallback_response.trace is None  # sanity: Slice A Analyzer leaves trace unset

    class _FakeAnalyzer:
        def analyze(self, text: str) -> AnalyzeResponse:
            return fallback_response

    monkeypatch.setattr(
        "app.analyze.graph_analyzer.Analyzer.from_settings",
        staticmethod(lambda: _FakeAnalyzer()),
    )

    fake_graph = MagicMock()
    fake_graph.invoke.side_effect = RuntimeError("Groq is down")

    result = GraphAnalyzer(graph=fake_graph).analyze("cannot connect to vpn")

    assert result.trace == {"enabled": False}
    assert result.debug is None


# ---------------------------------------------------------------------------
# LangSmith env export (C3)
# ---------------------------------------------------------------------------


def test_ensure_langsmith_env_exports_when_tracing_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tracing is on, Settings values are exported to os.environ for the SDK."""
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)

    settings = Settings(
        langsmith_tracing=True,
        langsmith_api_key="fake-key",
        langsmith_project="queuepilot-test",
        langsmith_endpoint="https://example.invalid",
    )

    _ensure_langsmith_env(settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "fake-key"
    assert os.environ["LANGSMITH_PROJECT"] == "queuepilot-test"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://example.invalid"


def test_ensure_langsmith_env_noop_when_tracing_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tracing is off, no environment variables are touched."""
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    settings = Settings(langsmith_tracing=False, langsmith_api_key="fake-key")

    _ensure_langsmith_env(settings)

    assert "LANGSMITH_TRACING" not in os.environ
    assert "LANGSMITH_API_KEY" not in os.environ
