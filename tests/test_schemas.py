"""A2 — output envelope schemas + request validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import AnalyzeRequest, AnalyzeResponse, SimilarTicket


def test_valid_request_strips_text() -> None:
    req = AnalyzeRequest(text="  printer offline  ", metadata={"channel": "email"})
    assert req.text == "printer offline"
    assert req.metadata == {"channel": "email"}


def test_empty_text_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest(text="   ")


def test_text_over_limit_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalyzeRequest(text="x" * 8001)  # default MAX_INPUT_CHARS = 8000


def test_response_reserved_fields_default_none() -> None:
    resp = AnalyzeResponse(confidence=0.5)
    # Slice A defaults
    assert resp.category is None
    assert resp.similar_tickets == []
    # reserved-for-later fields are None, not populated
    reserved = ("sentiment", "sla_risk", "escalate", "clarification", "suggested_reply", "trace")
    for field in reserved:
        assert getattr(resp, field) is None


def test_confidence_must_be_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        AnalyzeResponse(confidence=1.5)


def test_similar_ticket_minimal() -> None:
    st = SimilarTicket(score=0.9, snippet="vpn won't connect")
    assert st.score == 0.9
    assert st.queue is None
