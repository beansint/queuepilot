"""B7 — unit tests for pure scoring functions (no LLM, no network).

Covers:
  full_confidence:
    * output is always clamped to [0.0, 1.0].
    * consistency bonus is applied when llm_queue == majority_queue (both non-None).
    * consistency bonus is NOT applied when either queue is None.
    * consistency bonus is NOT applied when llm_queue != majority_queue.
    * missing penalty is applied when missing_count > 0.
    * high agreement + high score + consistency → high confidence.
    * low agreement + low score + no consistency → low confidence.

  sla_risk:
    * output is always clamped to [0.0, 1.0].
    * "high" priority yields higher risk than "low" priority (same frustration).
    * has_missing=True adds a non-zero contribution.
    * unknown priority falls back to the medium (0.5) weight.
    * None priority is treated as unknown (medium weight).
"""

from __future__ import annotations

import pytest

from app.analyze.scoring import (
    PENALTY_MISSING,
    W_CONSISTENCY,
    full_confidence,
    sla_risk,
)

# ---------------------------------------------------------------------------
# full_confidence
# ---------------------------------------------------------------------------


def test_full_confidence_clamped_high() -> None:
    """Extreme inputs must not push the result above 1.0."""
    conf = full_confidence(1000.0, 1.0, "IT", "IT", 0)
    assert conf <= 1.0


def test_full_confidence_clamped_low() -> None:
    """Extreme negative inputs must not push the result below 0.0."""
    conf = full_confidence(-1000.0, 0.0, None, None, 10)
    assert conf >= 0.0


def test_full_confidence_always_in_unit_interval() -> None:
    """full_confidence returns [0.0, 1.0] across a grid of inputs."""
    for top_score in (-5.0, 0.0, 0.5, 1.0, 10.0):
        for agreement in (0.0, 0.5, 1.0):
            for missing in (0, 3):
                conf = full_confidence(top_score, agreement, "Q", "Q", missing)
                assert 0.0 <= conf <= 1.0, (
                    f"Out of range for top_score={top_score}, agreement={agreement}, "
                    f"missing={missing}: {conf}"
                )


def test_full_confidence_consistency_bonus_applied() -> None:
    """When llm_queue == majority_queue (both non-None) the consistency bonus is added."""
    without = full_confidence(0.5, 0.5, "IT", None, 0)   # None majority → no bonus
    with_   = full_confidence(0.5, 0.5, "IT", "IT", 0)   # matching → bonus
    assert with_ == pytest.approx(without + W_CONSISTENCY, abs=1e-9)


def test_full_confidence_consistency_bonus_not_applied_when_none() -> None:
    """No bonus when either queue is None."""
    both_none = full_confidence(0.5, 0.5, None, None, 0)
    llm_none  = full_confidence(0.5, 0.5, None, "IT", 0)
    maj_none  = full_confidence(0.5, 0.5, "IT", None, 0)
    # All three should be equal (no bonus in any case)
    assert both_none == pytest.approx(llm_none, abs=1e-9)
    assert both_none == pytest.approx(maj_none, abs=1e-9)


def test_full_confidence_consistency_bonus_not_applied_when_mismatch() -> None:
    """No bonus when llm_queue != majority_queue."""
    matching  = full_confidence(0.5, 0.5, "IT",      "IT",      0)
    mismatch  = full_confidence(0.5, 0.5, "Billing",  "IT",      0)
    assert matching == pytest.approx(mismatch + W_CONSISTENCY, abs=1e-9)


def test_full_confidence_missing_penalty_applied() -> None:
    """A missing_count > 0 subtracts PENALTY_MISSING from the raw score."""
    no_missing   = full_confidence(0.5, 0.5, None, None, 0)
    with_missing = full_confidence(0.5, 0.5, None, None, 1)
    # Both are clamped, but if neither hits the boundary the difference equals PENALTY_MISSING.
    # (The unclamped difference must equal PENALTY_MISSING.)
    assert no_missing - with_missing == pytest.approx(PENALTY_MISSING, abs=1e-9)


def test_full_confidence_high_inputs_yield_high_result() -> None:
    """Perfect agreement + matching queues + no missing → confidence close to 1.0."""
    conf = full_confidence(10.0, 1.0, "IT", "IT", 0)
    assert conf > 0.9


def test_full_confidence_low_inputs_yield_low_result() -> None:
    """Low score, low agreement, mismatching queues → confidence well below 0.5."""
    conf = full_confidence(0.0, 0.0, "Billing", "IT", 0)
    # base = 0 + 0.3*sigmoid(0) = 0.3*0.5 = 0.15; no consistency, no penalty
    assert conf == pytest.approx(0.15, abs=1e-6)


def test_full_confidence_monotone_in_agreement() -> None:
    """Higher agreement (same other inputs) → higher or equal confidence."""
    low  = full_confidence(0.5, 0.2, "IT", "IT", 0)
    high = full_confidence(0.5, 0.9, "IT", "IT", 0)
    assert high >= low


def test_full_confidence_monotone_in_score() -> None:
    """Higher top_score (same other inputs) → higher or equal confidence."""
    low  = full_confidence(0.0, 0.5, None, None, 0)
    high = full_confidence(5.0, 0.5, None, None, 0)
    assert high >= low


def test_full_confidence_missing_two_items_same_as_one() -> None:
    """Penalty is binary (presence of missing info), not proportional to count."""
    one   = full_confidence(0.5, 0.5, None, None, 1)
    five  = full_confidence(0.5, 0.5, None, None, 5)
    assert one == pytest.approx(five, abs=1e-9)


# ---------------------------------------------------------------------------
# sla_risk
# ---------------------------------------------------------------------------


def test_sla_risk_clamped_high() -> None:
    """Extreme inputs must not push the result above 1.0."""
    risk = sla_risk("high", 1.0, True)
    assert risk <= 1.0


def test_sla_risk_clamped_low() -> None:
    """Minimum inputs must not push the result below 0.0."""
    risk = sla_risk("low", 0.0, False)
    assert risk >= 0.0


def test_sla_risk_always_in_unit_interval() -> None:
    """sla_risk returns [0.0, 1.0] across a grid of inputs."""
    for priority in ("high", "medium", "low", None, "unknown"):
        for frustration in (0.0, 0.5, 1.0):
            for has_missing in (True, False):
                risk = sla_risk(priority, frustration, has_missing)
                assert 0.0 <= risk <= 1.0, (
                    f"Out of range: priority={priority!r}, frustration={frustration}, "
                    f"has_missing={has_missing}: {risk}"
                )


def test_sla_risk_high_priority_greater_than_low() -> None:
    """High priority contributes more than low priority (same frustration + missing)."""
    low_p  = sla_risk("low",  0.3, False)
    high_p = sla_risk("high", 0.3, False)
    assert high_p > low_p


def test_sla_risk_has_missing_adds_contribution() -> None:
    """has_missing=True should yield a strictly higher risk than False (given headroom)."""
    without = sla_risk("low", 0.0, False)
    with_   = sla_risk("low", 0.0, True)
    assert with_ > without


def test_sla_risk_unknown_priority_uses_medium_weight() -> None:
    """An unknown priority string falls back to the same weight as 'medium'."""
    medium  = sla_risk("medium",       0.4, False)
    unknown = sla_risk("UNRECOGNISED", 0.4, False)
    none_p  = sla_risk(None,           0.4, False)
    assert medium == pytest.approx(unknown, abs=1e-9)
    assert medium == pytest.approx(none_p,  abs=1e-9)


def test_sla_risk_high_priority_high_frustration_exceeds_threshold() -> None:
    """High priority + high frustration must exceed the 0.7 escalation threshold."""
    risk = sla_risk("high", 0.9, False)
    assert risk > 0.7


def test_sla_risk_low_priority_low_frustration_below_threshold() -> None:
    """Low priority + low frustration should be comfortably below 0.7."""
    risk = sla_risk("low", 0.1, False)
    assert risk < 0.4


def test_sla_risk_exact_formula_low() -> None:
    """Verify the exact formula for a low-risk case."""
    # pw=0.2 (low), frustration=0.0, has_missing=False
    # = clamp01(0.5*0.2 + 0.3*0.0 + 0.2*0.0) = clamp01(0.1) = 0.1
    risk = sla_risk("low", 0.0, False)
    assert risk == pytest.approx(0.1, abs=1e-9)


def test_sla_risk_exact_formula_high_with_missing() -> None:
    """Verify the exact formula for a high-risk case with missing info."""
    # pw=1.0 (high), frustration=0.5, has_missing=True
    # = clamp01(0.5*1.0 + 0.3*0.5 + 0.2*1.0) = clamp01(0.5 + 0.15 + 0.2) = clamp01(0.85) = 0.85
    risk = sla_risk("high", 0.5, True)
    assert risk == pytest.approx(0.85, abs=1e-9)
