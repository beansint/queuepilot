"""D5 — unit tests for ``eval.evaluators.calibration`` (no network).

Covers:
  * ECE on a hand-computed example equals the expected value.
  * reliability_table bucket counts/midpoints are correct.
  * Parity: learn/10_calibration_demo's simulation numbers are reproducible via the
    shared functions (same import, same math, no drift).
"""

from __future__ import annotations

import pytest

from eval.evaluators.calibration import (
    DEFAULT_BUCKETS,
    calibration_summary,
    expected_calibration_error,
    reliability_table,
)

# ---------------------------------------------------------------------------
# Hand-computed ECE example
# ---------------------------------------------------------------------------


def test_ece_hand_computed_example() -> None:
    """4 pairs across two buckets with a known, hand-computed ECE.

    Bucket [0.0, 0.4): confidences 0.1, 0.3 -> correct=[True, False] -> acc=0.5, mid=0.2
        gap = |0.2 - 0.5| * 2 = 0.6
    Bucket [0.7, 1.01): confidences 0.9, 0.95 -> correct=[True, True] -> acc=1.0,
        mid=(0.7+1.01)/2=0.855 (below the 1.0 cap, so unaffected by it)
        gap = |0.855 - 1.0| * 2 = 0.29
    ECE = (0.6 + 0.29) / 4 = 0.2225
    """
    pairs = [(True, 0.1), (False, 0.3), (True, 0.9), (True, 0.95)]
    ece = expected_calibration_error(pairs)
    assert ece == 0.2225


def test_ece_perfect_calibration_is_zero() -> None:
    """If bucket accuracy exactly equals the bucket midpoint, ECE is 0."""
    # Bucket [0.4, 0.55): midpoint 0.475. 4 examples, correct fraction must equal 0.475
    # exactly isn't achievable with integers, so use a midpoint-friendly bucket instead:
    # [0.0, 0.4): midpoint 0.2 -> need accuracy 0.2 -> 1/5 correct.
    pairs = [(True, 0.1)] + [(False, 0.1)] * 4
    ece = expected_calibration_error(pairs)
    assert ece == 0.0


def test_ece_empty_pairs_is_zero() -> None:
    assert expected_calibration_error([]) == 0.0


# ---------------------------------------------------------------------------
# reliability_table
# ---------------------------------------------------------------------------


def test_reliability_table_bucket_counts_and_midpoints() -> None:
    pairs = [
        (True, 0.1),  # bucket [0.0, 0.4)
        (False, 0.35),  # bucket [0.0, 0.4)
        (True, 0.45),  # bucket [0.4, 0.55)
        (True, 0.9),  # bucket [0.7, 1.01)
    ]
    rows = reliability_table(pairs)

    by_lo = {row["lo"]: row for row in rows}
    assert by_lo[0.0]["n"] == 2
    assert by_lo[0.0]["accuracy"] == 0.5
    assert by_lo[0.0]["claimed"] == 0.2

    assert by_lo[0.4]["n"] == 1
    assert by_lo[0.4]["accuracy"] == 1.0

    assert by_lo[0.7]["n"] == 1
    assert by_lo[0.7]["accuracy"] == 1.0

    # bucket [0.55, 0.7) had no examples -> not present.
    assert 0.55 not in by_lo


def test_reliability_table_skips_empty_buckets() -> None:
    pairs = [(True, 0.1)]
    rows = reliability_table(pairs)
    assert len(rows) == 1
    assert rows[0]["lo"] == 0.0


def test_reliability_table_midpoint_capped_at_one() -> None:
    """A bucket whose raw midpoint exceeds 1.0 reports claimed=1.0, not the raw value."""
    pairs = [(True, 1.0)]
    rows = reliability_table(pairs, buckets=[(0.9, 1.3)])
    assert rows[0]["claimed"] == 1.0

    # Sanity: the *default* buckets never trigger the cap (0.7+1.01)/2 = 0.855 < 1.0.
    default_rows = reliability_table(pairs)
    assert default_rows[0]["claimed"] == 0.855


def test_default_buckets_match_learn_10_prototype() -> None:
    assert DEFAULT_BUCKETS == [(0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 1.01)]


# ---------------------------------------------------------------------------
# calibration_summary (LangSmith summary-evaluator shape)
# ---------------------------------------------------------------------------


def test_calibration_summary_skips_missing_reference_queue() -> None:
    outputs = [
        {"queue": "Billing", "confidence": 0.9},
        {"queue": "Technical Support", "confidence": 0.3},
    ]
    reference_outputs = [
        {"queue": "Billing"},
        {},  # edge case: no reference queue -> skipped
    ]
    result = calibration_summary(outputs, reference_outputs)
    # LangSmith's EvaluationResult is extra="forbid", so the summary evaluator must
    # return ONLY {"key", "score"} -- no "reliability" key (see eval/run_experiment.py's
    # _aggregate_metrics for the local reliability-table computation used by the card).
    # Only the first row has a reference queue: (correct=True, confidence=0.9) lands in
    # bucket [0.7, 1.01), midpoint 0.855, accuracy 1.0 -> ece = |0.855 - 1.0| = 0.145.
    assert result == {"key": "ece", "score": pytest.approx(0.145)}


def test_calibration_summary_correctness_is_case_insensitive() -> None:
    outputs = [{"queue": "billing", "confidence": 0.9}]
    reference_outputs = [{"queue": "Billing"}]
    result = calibration_summary(outputs, reference_outputs)
    # Single correct pair at confidence 0.9 -> bucket midpoint 0.855, accuracy 1.0.
    assert result == {"key": "ece", "score": pytest.approx(0.145)}


# ---------------------------------------------------------------------------
# Parity with learn/10_calibration_demo.py
# ---------------------------------------------------------------------------


def test_learn_10_numbers_reproducible_via_shared_functions() -> None:
    """Re-run learn/10's exact simulation and confirm the ECE values it prints are
    reproducible using the shared eval.evaluators.calibration functions — i.e. the
    demo script and the real evaluator share one implementation, not two that could
    silently drift apart."""
    import random

    from app.analyze.scoring import full_confidence_breakdown

    rng = random.Random(7)
    n_tickets = 600
    rows: list[tuple[bool, float, float]] = []
    for _ in range(n_tickets):
        agreement = rng.choice([0.2, 0.4, 0.6, 0.8, 1.0])
        top_score = rng.uniform(0.2, 0.85)
        missing = rng.random() < 0.30

        p_correct = 0.30 + 0.45 * agreement + 0.25 * (top_score - 0.5) - (0.12 if missing else 0.0)
        p_correct = max(0.0, min(1.0, p_correct))
        was_correct = rng.random() < p_correct

        self_conf = 0.95
        blended = full_confidence_breakdown(
            top_score=top_score,
            agreement=agreement,
            llm_queue="tech-support",
            majority_queue="tech-support",
            missing_count=1 if missing else 0,
        )["final"]

        rows.append((was_correct, self_conf, blended))

    self_pairs = [(c, s) for (c, s, _b) in rows]
    blended_pairs = [(c, b) for (c, _s, b) in rows]

    self_ece = expected_calibration_error(self_pairs)
    blended_ece = expected_calibration_error(blended_pairs)

    # These are the exact numbers learn/10_calibration_demo.py prints for seed=7,
    # N=600 (verified by running the script). The blended score must calibrate far
    # better (lower ECE) than the overconfident self-report.
    assert round(self_ece, 3) == 0.327
    assert round(blended_ece, 3) == 0.109
    assert blended_ece < self_ece
