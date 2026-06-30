"""A8 — LIVE integration test: real Analyzer.from_settings().analyze() call.

Skipped by default. Run explicitly with:

    QUEUEPILOT_RUN_INTEGRATION=1 uv run pytest -m integration -k analyze_integration

PREREQUISITE: the ingest pipeline (uv run python data/ingest.py) must have populated
the production Pinecone index before this test is run.  A 3k corpus ingest is a
prerequisite — do NOT run while ingest is still in progress.

DO NOT run this test manually during Slice-A development; Opus will run it after the
ingest finishes and the BM25 artifact is written to data/artifacts/bm25_params.json.
"""

from __future__ import annotations

import os

import pytest

from app.analyze.baseline import Analyzer

pytestmark = pytest.mark.integration

_RUN: bool = os.environ.get("QUEUEPILOT_RUN_INTEGRATION") == "1"


@pytest.mark.skipif(not _RUN, reason="set QUEUEPILOT_RUN_INTEGRATION=1 to run live /analyze test")
def test_analyze_real_query_vpn() -> None:
    """Real Analyzer returns a valid Slice-A envelope with non-empty similar_tickets."""
    analyzer = Analyzer.from_settings()
    result = analyzer.analyze("cannot connect to vpn from home")

    # Envelope completeness
    assert 0.0 <= result.confidence <= 1.0
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

    # Reserved Slice-B/C fields must remain None in Slice A
    assert result.sentiment is None
    assert result.sla_risk is None
    assert result.escalate is None
    assert result.clarification is None
    assert result.suggested_reply is None
    assert result.trace is None
