"""D7 — unit tests for the ``evaluate()`` target wrapper (no network).

Monkeypatches the lazy ``GraphAnalyzer`` singleton with a fake returning a known
``AnalyzeResponse`` and asserts the returned dict shape/keys, especially that
``type`` mirrors ``AnalyzeResponse.category`` (the system's queue-type -> category
mapping — see 11-SLICE-D-DESIGN.md task brief).
"""

from __future__ import annotations

import pytest

import eval.target as target_mod
from app.schemas import AnalyzeResponse, SimilarTicket
from eval.target import analyze_target


class _FakeAnalyzer:
    def __init__(self, response: AnalyzeResponse) -> None:
        self._response = response
        self.calls: list[str] = []

    def analyze(self, text: str) -> AnalyzeResponse:
        self.calls.append(text)
        return self._response


def _make_response() -> AnalyzeResponse:
    return AnalyzeResponse(
        category="Incident",
        queue="Technical Support",
        priority="high",
        confidence=0.82,
        similar_tickets=[
            SimilarTicket(
                score=0.9,
                queue="Technical Support",
                priority="high",
                type="Incident",
                snippet="s1",
            ),
        ],
        suggested_reply="Please try restarting the device.",
    )


def test_analyze_target_shape_and_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeAnalyzer(_make_response())
    monkeypatch.setattr(target_mod, "_get_analyzer", lambda: fake)

    result = analyze_target({"text": "my device is broken"})

    assert result["queue"] == "Technical Support"
    assert result["priority"] == "high"
    # `type` mirrors AnalyzeResponse.category (the ticket "type" label maps to category).
    assert result["type"] == "Incident"
    assert result["category"] == "Incident"
    assert result["confidence"] == pytest.approx(0.82)
    assert result["suggested_reply"] == "Please try restarting the device."
    assert fake.calls == ["my device is broken"]


def test_analyze_target_similar_tickets_are_plain_dicts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeAnalyzer(_make_response())
    monkeypatch.setattr(target_mod, "_get_analyzer", lambda: fake)

    result = analyze_target({"text": "x"})

    assert result["similar_tickets"] == [
        {
            "score": 0.9,
            "queue": "Technical Support",
            "priority": "high",
            "type": "Incident",
            "snippet": "s1",
        }
    ]
    assert all(isinstance(t, dict) for t in result["similar_tickets"])


def test_analyze_target_handles_none_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    response = AnalyzeResponse(category=None, queue=None, priority=None, confidence=0.0)
    fake = _FakeAnalyzer(response)
    monkeypatch.setattr(target_mod, "_get_analyzer", lambda: fake)

    result = analyze_target({"text": ""})

    assert result["queue"] is None
    assert result["type"] is None
    assert result["similar_tickets"] == []
    assert result["suggested_reply"] is None
