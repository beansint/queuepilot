"""Online eval runner (D10): grade recent production ``/analyze`` traces in place.

Pulls recent root runs of ``GraphAnalyzer.analyze`` from the configured LangSmith
project via ``client.list_runs(is_root=True, ...)``, runs the deterministic evaluators
(D4) + the calibration summary evaluator (D5) against their logged inputs/outputs, and
prints an aggregate snapshot card. Needs no eval dataset — it grades real traffic in
place, which is the "online" half of D11's offline-vs-online distinction.

CLI:
    uv run python -m eval.run_online --limit 20
"""

from __future__ import annotations

import argparse
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

_PER_EXAMPLE_EVALUATORS = [queue_match, priority_match, type_match, label_recall_at_k]


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
