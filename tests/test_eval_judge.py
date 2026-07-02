"""D6 — unit tests for the Gemini LLM-as-judge evaluator (no network).

Covers:
  * normal scoring: normalization to [0, 1] and the returned shape.
  * clamping of out-of-range / malformed judge scores.
  * graceful skip (dict with ``score: None``) when ``suggested_reply`` is empty.
  * graceful skip (dict with ``score: None``) when no Gemini key is configured
    (``_build_judge`` returns ``None``).

``reply_quality`` never returns bare ``None`` — LangSmith's ``evaluate()`` runner rejects
that (see ``langsmith.evaluation.evaluator._format_evaluator_result``).
"""

from __future__ import annotations

from typing import Any

import pytest

import eval.evaluators.judge as judge_mod
from eval.evaluators.judge import reply_quality


class _FakeJudge:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        self.calls.append((system, user))
        return self._result


_INPUTS = {"text": "My printer is broken"}
_OUTPUTS = {
    "suggested_reply": "Please try reinstalling the printer driver.",
    "similar_tickets": [{"queue": "IT", "snippet": "printer issue"}],
}
_REFERENCE = {"queue": "IT", "priority": "low", "type": "Incident"}


def test_reply_quality_normalizes_and_returns_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeJudge({"groundedness": 5, "helpfulness": 3, "rationale": "solid answer"})
    monkeypatch.setattr(judge_mod, "_build_judge", lambda: fake)

    result = reply_quality(_INPUTS, _OUTPUTS, _REFERENCE)

    assert result is not None
    assert result["key"] == "reply_quality"
    # groundedness=5 -> 1.0, helpfulness=3 -> 0.5 => mean 0.75
    assert result["score"] == pytest.approx(0.75)
    assert result["comment"] == "solid answer"


def test_reply_quality_clamps_out_of_range_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeJudge({"groundedness": 99, "helpfulness": -3, "rationale": "n/a"})
    monkeypatch.setattr(judge_mod, "_build_judge", lambda: fake)

    result = reply_quality(_INPUTS, _OUTPUTS, _REFERENCE)

    assert result is not None
    # groundedness clamped to 5 -> 1.0, helpfulness clamped to 1 -> 0.0 => mean 0.5
    assert result["score"] == pytest.approx(0.5)


def test_reply_quality_clamps_non_numeric_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeJudge({"groundedness": "high", "helpfulness": None, "rationale": ""})
    monkeypatch.setattr(judge_mod, "_build_judge", lambda: fake)

    result = reply_quality(_INPUTS, _OUTPUTS, _REFERENCE)

    assert result is not None
    # both fall back to the clamp floor (1) -> normalized 0.0 each => mean 0.0
    assert result["score"] == pytest.approx(0.0)


def test_reply_quality_none_when_suggested_reply_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeJudge({"groundedness": 5, "helpfulness": 5, "rationale": "x"})
    monkeypatch.setattr(judge_mod, "_build_judge", lambda: fake)

    outputs = {**_OUTPUTS, "suggested_reply": ""}
    result = reply_quality(_INPUTS, outputs, _REFERENCE)
    assert result == {"key": "reply_quality", "score": None, "comment": "no suggested_reply"}

    outputs_missing = {"similar_tickets": []}
    result_missing = reply_quality(_INPUTS, outputs_missing, _REFERENCE)
    assert result_missing["key"] == "reply_quality"
    assert result_missing["score"] is None

    outputs_whitespace = {**_OUTPUTS, "suggested_reply": "   "}
    result_whitespace = reply_quality(_INPUTS, outputs_whitespace, _REFERENCE)
    assert result_whitespace["key"] == "reply_quality"
    assert result_whitespace["score"] is None


def test_reply_quality_none_when_no_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(judge_mod, "_build_judge", lambda: None)
    result = reply_quality(_INPUTS, _OUTPUTS, _REFERENCE)
    assert result["key"] == "reply_quality"
    assert result["score"] is None


def test_build_judge_returns_none_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(judge_mod, "get_settings", lambda: Settings(gemini_api_key=None))
    assert judge_mod._build_judge() is None


def test_build_judge_builds_gemini_chat_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(judge_mod, "get_settings", lambda: Settings(gemini_api_key="k"))
    judge = judge_mod._build_judge()
    assert judge is not None
    assert isinstance(judge, judge_mod.GeminiChat)
