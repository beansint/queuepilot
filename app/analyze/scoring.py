"""Pure scoring functions for Slice B (B7).

All functions are deterministic and free of I/O — no LLM, no network.
Reuses ``_sigmoid`` and ``_clamp01`` from ``baseline`` to keep a single source of truth.

Weights and thresholds are module constants so they can be imported by tests and the
learning script without instantiating the full graph.
"""

from __future__ import annotations

from typing import Any

from app.analyze.baseline import _clamp01, _sigmoid

# ---------------------------------------------------------------------------
# Confidence blend weights
# ---------------------------------------------------------------------------

#: Weight for retrieval label-agreement fraction (fraction of neighbors sharing winning queue).
W_AGREEMENT: float = 0.5
#: Weight for sigmoid-scaled top retrieval score.
W_SCORE: float = 0.3
#: Bonus applied when the LLM-classified queue matches the majority-vote queue (both non-None).
W_CONSISTENCY: float = 0.2

#: Penalty subtracted when assess_missing found at least one missing detail.
PENALTY_MISSING: float = 0.15

# ---------------------------------------------------------------------------
# SLA-risk blend weights
# ---------------------------------------------------------------------------

#: Weight for the numeric priority tier.
SLA_W_PRIORITY: float = 0.5
#: Weight for the customer-frustration sentiment score.
SLA_W_FRUSTRATION: float = 0.3
#: Weight for the presence of missing information.
SLA_W_MISSING: float = 0.2

#: Map priority label → numeric weight; unknown / None labels default to medium (0.5).
_PRIORITY_WEIGHTS: dict[str, float] = {"high": 1.0, "medium": 0.5, "low": 0.2}


def full_confidence(
    top_score: float,
    agreement: float,
    llm_queue: str | None,
    majority_queue: str | None,
    missing_count: int,
) -> float:
    """Blended confidence: retrieval strength + label consistency − missing-info penalty.

    Formula::

        base        = W_AGREEMENT * agreement + W_SCORE * sigmoid(top_score)
        consistency = W_CONSISTENCY if llm_queue == majority_queue (both non-None) else 0.0
        penalty     = PENALTY_MISSING if missing_count > 0 else 0.0
        return      clamp01(base + consistency - penalty)

    Args:
        top_score:      Hybrid retrieval score of the top-ranked neighbor.
        agreement:      Fraction of neighbors that share the winning queue (from majority_vote).
        llm_queue:      Queue label produced by the LLM classify node (may be None).
        majority_queue: Queue label from majority_vote over the same neighbor set (may be None).
        missing_count:  Number of items flagged as missing by the assess_missing node.

    Returns:
        Float clamped to ``[0.0, 1.0]``.
    """
    base = W_AGREEMENT * agreement + W_SCORE * _sigmoid(top_score)
    consistency = (
        W_CONSISTENCY
        if (
            llm_queue is not None
            and majority_queue is not None
            and llm_queue == majority_queue
        )
        else 0.0
    )
    penalty = PENALTY_MISSING if missing_count > 0 else 0.0
    return _clamp01(base + consistency - penalty)


def full_confidence_breakdown(
    top_score: float,
    agreement: float,
    llm_queue: str | None,
    majority_queue: str | None,
    missing_count: int,
) -> dict[str, Any]:
    """Same computation as ``full_confidence`` but returns every intermediate term.

    Used by the ``score`` node's ``--explain`` accumulator (C4). Kept as a sibling
    function (rather than changing ``full_confidence``'s return type) so existing
    callers/tests of ``full_confidence`` are unaffected.

    Returns:
        A dict with ``agreement``, ``top_score``, ``sigmoid_top_score``, ``consistency``,
        ``penalty``, ``final``, and the weight constants used (``w_agreement``,
        ``w_score``, ``w_consistency``, ``penalty_missing``).
    """
    sigmoid_top_score = _sigmoid(top_score)
    base = W_AGREEMENT * agreement + W_SCORE * sigmoid_top_score
    consistency = (
        W_CONSISTENCY
        if (
            llm_queue is not None
            and majority_queue is not None
            and llm_queue == majority_queue
        )
        else 0.0
    )
    penalty = PENALTY_MISSING if missing_count > 0 else 0.0
    final = _clamp01(base + consistency - penalty)
    return {
        "agreement": agreement,
        "top_score": top_score,
        "sigmoid_top_score": sigmoid_top_score,
        "consistency": consistency,
        "penalty": penalty,
        "final": final,
        "w_agreement": W_AGREEMENT,
        "w_score": W_SCORE,
        "w_consistency": W_CONSISTENCY,
        "penalty_missing": PENALTY_MISSING,
    }


def sla_risk(
    priority: str | None,
    frustration: float,
    has_missing: bool,
) -> float:
    """SLA risk score combining ticket priority, customer frustration, and missing information.

    Formula::

        pw     = priority_weight[priority.lower()]  (default 0.5 for unknown/None)
        return clamp01(SLA_W_PRIORITY * pw
                       + SLA_W_FRUSTRATION * frustration
                       + SLA_W_MISSING * (1.0 if has_missing else 0.0))

    Args:
        priority:    Ticket priority label (case-insensitive; "high" / "medium" / "low").
        frustration: Customer frustration score in [0.0, 1.0] from the sentiment node.
        has_missing: True when assess_missing returned a non-empty list.

    Returns:
        Float clamped to ``[0.0, 1.0]``.
    """
    pw = _PRIORITY_WEIGHTS.get((priority or "").lower(), 0.5)
    return _clamp01(
        SLA_W_PRIORITY * pw
        + SLA_W_FRUSTRATION * frustration
        + SLA_W_MISSING * (1.0 if has_missing else 0.0)
    )


def sla_risk_breakdown(
    priority: str | None,
    frustration: float,
    has_missing: bool,
) -> dict[str, Any]:
    """Same computation as ``sla_risk`` but returns every intermediate term.

    Used by the ``score`` node's ``--explain`` accumulator (C4). Kept as a sibling
    function so ``sla_risk`` itself is unchanged (backward-compatible with existing tests).

    Returns:
        A dict with ``priority``, ``priority_weight``, ``frustration``, ``has_missing``,
        ``final``, and the weight constants used (``w_priority``, ``w_frustration``,
        ``w_missing``).
    """
    pw = _PRIORITY_WEIGHTS.get((priority or "").lower(), 0.5)
    final = _clamp01(
        SLA_W_PRIORITY * pw
        + SLA_W_FRUSTRATION * frustration
        + SLA_W_MISSING * (1.0 if has_missing else 0.0)
    )
    return {
        "priority": priority,
        "priority_weight": pw,
        "frustration": frustration,
        "has_missing": has_missing,
        "final": final,
        "w_priority": SLA_W_PRIORITY,
        "w_frustration": SLA_W_FRUSTRATION,
        "w_missing": SLA_W_MISSING,
    }
