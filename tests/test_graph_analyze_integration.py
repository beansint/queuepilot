"""B11 — LIVE integration test: real GraphAnalyzer through the full LangGraph workflow.

Skipped by default. Run explicitly with:

    QUEUEPILOT_RUN_INTEGRATION=1 uv run pytest -m integration -k graph_analyze_integration

PREREQUISITES:
  - The ingest pipeline (uv run python data/ingest.py) must have populated the
    Pinecone index and written data/artifacts/bm25_params.json.
  - All required API keys must be present in .env (VOYAGE_API_KEY, PINECONE_API_KEY,
    GROQ_API_KEY for the default chat model).

DO NOT run this test during offline development.  Opus runs it after verifying that the
live index and artifact are available.
"""

from __future__ import annotations

import os

import pytest

from app.analyze.graph_analyzer import GraphAnalyzer
from app.schemas import AnalyzeResponse

pytestmark = pytest.mark.integration

_RUN: bool = os.environ.get("QUEUEPILOT_RUN_INTEGRATION") == "1"


@pytest.mark.skipif(
    not _RUN,
    reason="set QUEUEPILOT_RUN_INTEGRATION=1 to run the live graph-analyze integration test",
)
def test_graph_analyze_real_query_vpn() -> None:
    """Real GraphAnalyzer returns a valid, populated Slice-B envelope for a VPN query."""
    analyzer = GraphAnalyzer.from_settings()
    result = analyzer.analyze("cannot connect to vpn from home")

    assert isinstance(result, AnalyzeResponse)

    # confidence is always in [0, 1]
    assert 0.0 <= result.confidence <= 1.0, (
        f"confidence out of range: {result.confidence}"
    )

    # similar_tickets must be non-empty against a populated corpus
    assert isinstance(result.similar_tickets, list)
    assert len(result.similar_tickets) > 0, (
        "expected non-empty similar_tickets for a VPN query against the 3k corpus"
    )

    # similar_tickets are ordered by descending score
    scores = [t.score for t in result.similar_tickets]
    assert scores == sorted(scores, reverse=True), (
        "similar_tickets must be in descending score order"
    )

    # Each ticket has required fields
    for ticket in result.similar_tickets:
        assert isinstance(ticket.score, float)
        assert isinstance(ticket.snippet, str)

    # Slice-B fields: at least one of the "decision-driven" group must be set,
    # proving the graph ran to completion rather than short-circuiting.
    #
    # A valid run sets either:
    #   - suggested_reply (answer path)
    #   - clarification (clarify path)
    #   - escalate = True (escalate path)
    decision_field_set = any([
        result.suggested_reply is not None,
        result.clarification is not None,
        result.escalate is True,
    ])
    assert decision_field_set, (
        "expected at least one decision-driven field (suggested_reply, clarification, "
        f"or escalate=True) to be set; got: suggested_reply={result.suggested_reply!r}, "
        f"clarification={result.clarification!r}, escalate={result.escalate!r}"
    )

    # category / queue / priority must be set (classify node ran)
    assert result.category is not None or result.queue is not None, (
        "expected classify node to set at least category or queue"
    )

    # trace reflects LangSmith tracing status (Slice C); disabled unless LANGSMITH_TRACING
    # + LANGSMITH_API_KEY are set in the environment running this live integration test.
    assert result.trace is not None and "enabled" in result.trace, (
        f"expected a trace summary dict with an 'enabled' key, got: {result.trace!r}"
    )
