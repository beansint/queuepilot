"""Online eval runner (D10): grade recent production ``/analyze`` traces in place.

Pulls recent root runs of ``GraphAnalyzer.analyze`` from the configured LangSmith
project via ``client.list_runs(is_root=True, ...)``, runs the deterministic evaluators
(D4) + the calibration summary evaluator (D5) against their logged inputs/outputs, and
prints an aggregate snapshot card. Needs no eval dataset — it grades real traffic in
place, which is the "online" half of D11's offline-vs-online distinction.

Reference-based metrics (exact-match / label-recall / ECE) need LABELED traces (a known
``queue``/``priority``/``type``), which raw production traffic does not carry — they are
correctly "n/a" here, and this module prints an explicit note explaining why so the "n/a"
reads as "expected", not "broken". The genuine online signal this module DOES produce is
aggregated human feedback: it reads each fetched run's ``user_thumbs`` feedback (attached
via ``POST /feedback``, see ``app.feedback``) via ``client.list_feedback(run_ids=...,
feedback_key=["user_thumbs"])`` and reports a satisfaction rate (mean thumbs score) + count.

CLI:
    uv run python -m eval.run_online --limit 20
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from app.config import get_settings
from eval.card import build_card
from eval.client import get_langsmith_client
from eval.evaluators import (
    calibration_summary,
    label_recall_at_k,
    priority_match,
    queue_match,
    type_match,
)

_logger = logging.getLogger(__name__)

_PER_EXAMPLE_EVALUATORS = [queue_match, priority_match, type_match, label_recall_at_k]

_REFERENCE_METRICS_NOTE = (
    "NOTE: reference-based metrics (queue/priority/type exact-match, label-recall@k, ECE) "
    "require LABELED traces (a known ground-truth queue/priority/type) and are correctly "
    "n/a here — raw production traffic carries no reference labels. Use "
    "`eval.run_experiment` (the offline runner) against the labeled eval dataset for those "
    "numbers. The genuine online signal below is aggregated human feedback (`user_thumbs`)."
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run QueuePilot online eval against recent /analyze traces."
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="Max recent root runs to grade (default: 20)."
    )
    return parser.parse_args(argv)


def _run_inputs_outputs(run: Any) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Extract ``(inputs, outputs)`` from a LangSmith ``Run``, or ``None`` if unusable."""
    inputs = getattr(run, "inputs", None) or {}
    outputs = getattr(run, "outputs", None) or {}
    if not inputs or not outputs:
        return None
    # GraphAnalyzer.analyze is traced as `_run(ticket_text)`; normalize to the
    # `{"text": ...}` shape the evaluators expect.
    if "text" not in inputs:
        ticket_text = inputs.get("ticket_text") or next(iter(inputs.values()), None)
        if isinstance(ticket_text, str):
            inputs = {**inputs, "text": ticket_text}
    return inputs, outputs


def _aggregate_human_feedback(client: Any, run_ids: list[str]) -> dict[str, Any] | None:
    """Read ``user_thumbs`` feedback for *run_ids* and return ``{"mean", "n"}``, or ``None``.

    Uses ``client.list_feedback(run_ids=..., feedback_key=["user_thumbs"])`` (the
    installed ``langsmith`` SDK's read API for feedback objects — confirmed against the
    installed ``Client.list_feedback`` signature, which filters by ``run_ids`` and
    ``feedback_key``). Returns ``None`` (never a fabricated 0.0) when there are no run ids,
    the read fails, or no run in the batch has any ``user_thumbs`` feedback yet — callers
    must render that as "n/a", not a real metric.
    """
    if not run_ids:
        return None
    try:
        feedback_items = list(
            client.list_feedback(run_ids=run_ids, feedback_key=["user_thumbs"])
        )
    except Exception:
        _logger.warning("run_online: client.list_feedback failed; human feedback n/a.")
        return None

    scores = [
        float(item.score) for item in feedback_items if isinstance(item.score, int | float)
    ]
    if not scores:
        return None
    return {"mean": sum(scores) / len(scores), "n": len(scores)}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    client = get_langsmith_client()
    if client is None:
        print(
            "run_online: no LangSmith client available (LANGSMITH_API_KEY not set). "
            "Cannot pull production traces.",
            file=sys.stderr,
        )
        return 1

    project_name = get_settings().langsmith_project
    runs = list(
        client.list_runs(
            project_name=project_name,
            is_root=True,
            run_type="chain",
            limit=args.limit,
        )
    )

    run_ids = [str(run.id) for run in runs if getattr(run, "id", None) is not None]

    print(_REFERENCE_METRICS_NOTE)
    human_feedback = _aggregate_human_feedback(client, run_ids)
    if human_feedback is not None:
        print(
            f"Human feedback (user_thumbs): mean={human_feedback['mean']:.3f} "
            f"over n={human_feedback['n']} rated run(s) (of {len(run_ids)} fetched)."
        )
    else:
        print(
            f"Human feedback (user_thumbs): n/a — no user_thumbs feedback found on the "
            f"{len(run_ids)} fetched run(s) yet."
        )

    pairs = [_run_inputs_outputs(run) for run in runs]
    usable = [p for p in pairs if p is not None]

    if not usable:
        print(
            f"run_online: no usable /analyze root runs found in project {project_name!r} "
            "(need runs with logged inputs and outputs). Nothing to grade.",
            file=sys.stderr,
        )
        return 0

    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    reference_outputs_list: list[dict[str, Any]] = []
    outputs_list: list[dict[str, Any]] = []

    for inputs, outputs in usable:
        # Online eval has no ground-truth reference labels; reference_outputs is empty
        # so exact-match/recall evaluators correctly no-op (return None) per their
        # documented skip convention. Calibration still works: it only needs `outputs`.
        reference_outputs: dict[str, Any] = {}
        outputs_list.append(outputs)
        reference_outputs_list.append(reference_outputs)
        for evaluator in _PER_EXAMPLE_EVALUATORS:
            result = evaluator(inputs, outputs, reference_outputs)
            if result is None:
                continue
            key = result["key"]
            score = result.get("score")
            if isinstance(score, int | float):
                sums[key] = sums.get(key, 0.0) + float(score)
                counts[key] = counts.get(key, 0) + 1

    metrics: dict[str, Any] = {
        "n": len(usable),
        "config": {"project": project_name, "mode": "online"},
        "human_feedback": human_feedback,
    }
    for key, total in sums.items():
        metrics[key] = total / counts[key] if counts.get(key) else None

    # Calibration needs (correct, confidence) pairs, and "correct" needs a reference
    # queue. Online traces usually have none, so ECE is only reported when at least one
    # run carries a reference queue — otherwise it is left absent (rendered "n/a"),
    # never shown as a misleading 0.0 over an empty pair set.
    has_calibration_pairs = any(ref.get("queue") for ref in reference_outputs_list)
    if has_calibration_pairs:
        summary = calibration_summary(outputs_list, reference_outputs_list)
        if isinstance(summary.get("score"), int | float):
            metrics["ece"] = float(summary["score"])

    card = build_card(metrics)
    print(card["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
