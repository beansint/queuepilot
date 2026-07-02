"""Calibration evaluator: reliability tables + Expected Calibration Error (D5).

Single source of truth for calibration math, shared by:
  * ``eval.evaluators.calibration.calibration_summary`` — the LangSmith summary
    evaluator run over a full offline experiment (validates the Slice A/B confidence
    blend on real model outputs), and
  * ``learn/10_calibration_demo.py`` — the standalone teaching script, which imports
    ``reliability_table`` / ``expected_calibration_error`` from here instead of
    reimplementing the bucketing logic.

Default buckets and the ECE definition below intentionally match the original
``learn/10_calibration_demo.py`` prototype so both consumers agree exactly.
"""

from __future__ import annotations

from typing import Any

#: (lo, hi) confidence buckets, half-open [lo, hi). The final bucket's upper bound
#: (1.01) intentionally exceeds 1.0 so a confidence of exactly 1.0 is still included.
DEFAULT_BUCKETS: list[tuple[float, float]] = [(0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 1.01)]


def reliability_table(
    pairs: list[tuple[bool, float]], buckets: list[tuple[float, float]] | None = None
) -> list[dict[str, Any]]:
    """Bucket ``(correct, confidence)`` pairs and compute per-bucket accuracy.

    Args:
        pairs: ``(was_correct, confidence)`` tuples.
        buckets: ``(lo, hi)`` half-open confidence ranges. Defaults to ``DEFAULT_BUCKETS``.

    Returns:
        One row per non-empty bucket: ``{"lo", "hi", "n", "claimed", "accuracy"}`` where
        ``claimed`` is the bucket midpoint (capped at 1.0) and ``accuracy`` is the
        fraction of examples in that bucket that were actually correct.
    """
    resolved_buckets = buckets if buckets is not None else DEFAULT_BUCKETS
    rows: list[dict[str, Any]] = []
    for lo, hi in resolved_buckets:
        selected = [correct for (correct, confidence) in pairs if lo <= confidence < hi]
        if not selected:
            continue
        accuracy = sum(selected) / len(selected)
        midpoint = min((lo + hi) / 2, 1.0)
        rows.append(
            {
                "lo": lo,
                "hi": hi,
                "n": len(selected),
                "claimed": midpoint,
                "accuracy": accuracy,
            }
        )
    return rows


def expected_calibration_error(
    pairs: list[tuple[bool, float]], buckets: list[tuple[float, float]] | None = None
) -> float:
    """Expected Calibration Error: weighted mean |claimed - accuracy| across buckets.

    ``ECE = sum_over_buckets(|claimed - accuracy| * n_in_bucket) / total_n``. Lower is
    better; 0.0 means "70% confident" really does mean "right ~70% of the time".
    """
    total = len(pairs)
    if total == 0:
        return 0.0
    rows = reliability_table(pairs, buckets)
    weighted_gap: float = sum(
        abs(float(row["claimed"]) - float(row["accuracy"])) * int(row["n"]) for row in rows
    )
    return weighted_gap / total


def calibration_summary(
    outputs: list[dict[str, Any]], reference_outputs: list[dict[str, Any]]
) -> dict[str, Any]:
    """LangSmith summary evaluator: ECE + reliability table over a full experiment run.

    Unlike the per-example evaluators in ``eval.evaluators.deterministic``, a summary
    evaluator receives the *entire* run's outputs/reference_outputs and scores the run
    as a whole — appropriate here because calibration is only meaningful in aggregate.

    Builds ``(correct, confidence)`` pairs where ``correct`` is queue exact-match
    (case-insensitive) and ``confidence`` is ``outputs["confidence"]``, skipping any
    example with no reference queue (e.g. hand-authored edge cases).

    Returns:
        ``{"key": "ece", "score": <ece>}``. LangSmith's ``EvaluationResult`` model is
        ``extra="forbid"``, so this must NOT carry a ``reliability`` key — a caller that
        wants the reliability table should call ``reliability_table`` directly (as
        ``eval.run_experiment._aggregate_metrics`` does, locally, over the same pairs).
    """
    pairs: list[tuple[bool, float]] = []
    for output, reference in zip(outputs, reference_outputs, strict=False):
        reference_queue = reference.get("queue")
        if not reference_queue:
            continue
        predicted_queue = output.get("queue")
        correct = (
            isinstance(predicted_queue, str)
            and predicted_queue.strip().lower() == str(reference_queue).strip().lower()
        )
        confidence = output.get("confidence")
        if not isinstance(confidence, int | float):
            continue
        pairs.append((correct, float(confidence)))

    ece = expected_calibration_error(pairs)
    return {"key": "ece", "score": ece}
