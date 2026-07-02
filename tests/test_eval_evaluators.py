"""D4 — unit tests for deterministic evaluators (no network).

Covers:
  * queue_match / priority_match / type_match: hit, miss, and the skip dict
    (``score: None``) when there is no reference.
  * label_recall_at_k: hit within top-k, miss, and the skip dict when there is no
    reference.

Evaluators never return bare ``None`` — LangSmith's ``evaluate()`` runner rejects that
(see ``langsmith.evaluation.evaluator._format_evaluator_result``). A "skip" is a dict
with ``score: None`` instead, so the metric key stays numeric-typed across rows.
"""

from __future__ import annotations

from eval.evaluators.deterministic import (
    label_recall_at_k,
    priority_match,
    queue_match,
    type_match,
)

# ---------------------------------------------------------------------------
# queue_match / priority_match / type_match
# ---------------------------------------------------------------------------


def test_queue_match_hit_case_insensitive() -> None:
    result = queue_match({}, {"queue": "technical support"}, {"queue": "Technical Support"})
    assert result == {"key": "queue_match", "score": 1.0}


def test_queue_match_miss() -> None:
    result = queue_match({}, {"queue": "Billing"}, {"queue": "Technical Support"})
    assert result == {"key": "queue_match", "score": 0.0}


def test_queue_match_none_when_no_reference() -> None:
    for reference in ({}, {"queue": None}, {"queue": ""}):
        result = queue_match({}, {"queue": "Billing"}, reference)
        assert result["key"] == "queue_match"
        assert result["score"] is None


def test_priority_match_hit_and_miss() -> None:
    assert priority_match({}, {"priority": "High"}, {"priority": "high"}) == {
        "key": "priority_match",
        "score": 1.0,
    }
    assert priority_match({}, {"priority": "low"}, {"priority": "high"}) == {
        "key": "priority_match",
        "score": 0.0,
    }


def test_priority_match_none_when_no_reference() -> None:
    result = priority_match({}, {"priority": "high"}, {})
    assert result["key"] == "priority_match"
    assert result["score"] is None


def test_type_match_hit_and_miss() -> None:
    assert type_match({}, {"type": "incident"}, {"type": "Incident"}) == {
        "key": "type_match",
        "score": 1.0,
    }
    assert type_match({}, {"type": "Request"}, {"type": "Incident"}) == {
        "key": "type_match",
        "score": 0.0,
    }


def test_type_match_none_when_no_reference() -> None:
    result = type_match({}, {"type": "Incident"}, {})
    assert result["key"] == "type_match"
    assert result["score"] is None


def test_queue_match_none_when_prediction_missing() -> None:
    """Missing prediction (never happened, e.g. graph error) still scores 0, not None."""
    result = queue_match({}, {}, {"queue": "Technical Support"})
    assert result == {"key": "queue_match", "score": 0.0}


# ---------------------------------------------------------------------------
# label_recall_at_k
# ---------------------------------------------------------------------------


def test_label_recall_at_k_hit() -> None:
    outputs = {
        "similar_tickets": [
            {"queue": "Billing"},
            {"queue": "Technical Support"},
            {"queue": "General Inquiry"},
        ]
    }
    result = label_recall_at_k({}, outputs, {"queue": "Technical Support"})
    assert result == {"key": "label_recall_at_k", "score": 1.0}


def test_label_recall_at_k_miss() -> None:
    outputs = {
        "similar_tickets": [
            {"queue": "Billing"},
            {"queue": "General Inquiry"},
        ]
    }
    result = label_recall_at_k({}, outputs, {"queue": "Technical Support"})
    assert result == {"key": "label_recall_at_k", "score": 0.0}


def test_label_recall_at_k_respects_k(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A hit beyond k must not count."""
    from eval import settings as settings_module

    class _FakeEvalSettings:
        recall_k = 2

    monkeypatch.setattr(settings_module, "get_eval_settings", lambda: _FakeEvalSettings())
    # Also patch the evaluator module's imported reference.
    import eval.evaluators.deterministic as det_module

    monkeypatch.setattr(det_module, "get_eval_settings", lambda: _FakeEvalSettings())

    outputs = {
        "similar_tickets": [
            {"queue": "Billing"},
            {"queue": "General Inquiry"},
            {"queue": "Technical Support"},  # index 2, beyond k=2
        ]
    }
    result = label_recall_at_k({}, outputs, {"queue": "Technical Support"})
    assert result == {"key": "label_recall_at_k", "score": 0.0}


def test_label_recall_at_k_none_when_no_reference() -> None:
    outputs = {"similar_tickets": [{"queue": "Billing"}]}
    result = label_recall_at_k({}, outputs, {})
    assert result["key"] == "label_recall_at_k"
    assert result["score"] is None


def test_label_recall_at_k_empty_neighbors() -> None:
    result = label_recall_at_k({}, {"similar_tickets": []}, {"queue": "Technical Support"})
    assert result == {"key": "label_recall_at_k", "score": 0.0}
