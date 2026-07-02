"""Deterministic, offline-testable evaluators (D4).

LangSmith-style evaluator signature: ``(inputs, outputs, reference_outputs) -> dict``.

LangSmith's ``evaluate()`` runner REJECTS a bare ``None`` return (see
``langsmith.evaluation.evaluator._format_evaluator_result``, which raises
``ValueError`` on falsy/``None`` results). So instead of returning ``None`` to "skip"
an example with no reference label (e.g. the hand-authored edge cases), every evaluator
here returns a dict with ``score: None`` and an explanatory ``comment``. This keeps the
metric's ``key`` consistently numeric-typed across rows (never mixing a numeric
``score`` with a categorical ``value`` under the same key), while still being a valid,
non-``None``, non-empty dict that LangSmith will accept and record as "no score" for
that row.
"""

from __future__ import annotations

from typing import Any

from eval.settings import get_eval_settings


def _case_insensitive_match(a: Any, b: Any) -> bool:
    """Compare two label values case-insensitively; both must be non-empty strings."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return a.strip().lower() == b.strip().lower()


def _field_match_evaluator(
    key: str, field: str, outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Shared implementation for the three exact-match evaluators."""
    reference_value = reference_outputs.get(field)
    if not reference_value:
        return {"key": key, "score": None, "comment": f"no reference {field}"}
    predicted_value = outputs.get(field)
    score = 1.0 if _case_insensitive_match(predicted_value, reference_value) else 0.0
    return {"key": key, "score": score}


def queue_match(
    inputs: dict[str, Any], outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Case-insensitive exact match on ``queue``. Skip dict when no reference queue."""
    return _field_match_evaluator("queue_match", "queue", outputs, reference_outputs)


def priority_match(
    inputs: dict[str, Any], outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Case-insensitive exact match on ``priority``. Skip dict when no reference priority."""
    return _field_match_evaluator("priority_match", "priority", outputs, reference_outputs)


def type_match(
    inputs: dict[str, Any], outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Case-insensitive exact match on ``type``. Skip dict when no reference type."""
    return _field_match_evaluator("type_match", "type", outputs, reference_outputs)


def label_recall_at_k(
    inputs: dict[str, Any], outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Label-recall@k: did any of the top-k retrieved neighbors share the reference queue?

    This is a documented PROXY for retrieval recall — we have no gold "relevant document
    ids" for the Kaggle corpus, so instead of measuring "was the *correct* neighbor
    retrieved" we measure the reproducible, honest stand-in: "was a neighbor with the
    *same queue label* as the reference among the top-k". ``k`` is read from
    ``EvalSettings.recall_k``. Returns the skip dict (``score: None``) when there is no
    reference queue (e.g. edge cases), matching the other evaluators' skip convention.
    """
    reference_queue = reference_outputs.get("queue")
    if not reference_queue:
        return {"key": "label_recall_at_k", "score": None, "comment": "no reference queue"}

    k = get_eval_settings().recall_k
    neighbors = outputs.get("similar_tickets") or []
    top_k = neighbors[:k]

    hit = any(
        _case_insensitive_match(neighbor.get("queue"), reference_queue)
        for neighbor in top_k
        if isinstance(neighbor, dict)
    )
    return {"key": "label_recall_at_k", "score": 1.0 if hit else 0.0}
