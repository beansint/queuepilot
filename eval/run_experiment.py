"""Offline experiment runner (D7): ``evaluate()`` over the eval dataset + config knobs.

CLI:
    uv run python -m eval.run_experiment --alpha 0.5 --chat groq --limit 20

Sets ``HYBRID_ALPHA`` / ``CHAT_PROVIDER`` env vars before building the graph (via
``app.config.get_settings.cache_clear()``) so the requested config actually takes
effect, uploads the dataset if needed, runs ``client.evaluate()`` with the D4-D6
evaluators + the D5 calibration summary evaluator, then writes a snapshot card (D8).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from app.config import get_settings
from eval.card import write_card
from eval.client import get_langsmith_client
from eval.dataset import build_eval_dataset
from eval.evaluators import (
    calibration_summary,
    label_recall_at_k,
    priority_match,
    queue_match,
    reply_quality,
    type_match,
)
from eval.evaluators.calibration import expected_calibration_error, reliability_table
from eval.settings import get_eval_settings
from eval.upload import upload_dataset

_logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a QueuePilot offline eval experiment.")
    parser.add_argument("--alpha", type=float, default=None, help="HYBRID_ALPHA override.")
    parser.add_argument("--chat", type=str, default=None, help="CHAT_PROVIDER override.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Cap the number of dataset examples used."
    )
    parser.add_argument(
        "--data", type=str, default=None, help="Dataset name override (default: EvalSettings)."
    )
    return parser.parse_args(argv)


def _apply_config(*, alpha: float | None, chat: str | None) -> dict[str, Any]:
    """Set env var overrides and clear the settings cache so the graph picks them up."""
    metadata: dict[str, Any] = {}
    if alpha is not None:
        os.environ["HYBRID_ALPHA"] = str(alpha)
        metadata["alpha"] = alpha
    if chat is not None:
        os.environ["CHAT_PROVIDER"] = chat
        metadata["chat"] = chat
    get_settings.cache_clear()
    resolved = get_settings()
    metadata.setdefault("alpha", resolved.hybrid_alpha)
    metadata.setdefault("chat", resolved.chat_provider)
    return metadata


def _result_field(result: Any, field: str) -> Any:
    """Read *field* off an evaluator result, whether it's a plain dict or a pydantic model."""
    if isinstance(result, dict):
        return result.get(field)
    return getattr(result, field, None)


def _row_field(row: Any, key: str) -> Any:
    """Read *key* off an ``ExperimentResultRow``, whether it's a plain dict or an object."""
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _aggregate_metrics(results: Any, *, n: int, config: dict[str, Any]) -> dict[str, Any]:
    """Reduce a LangSmith ``ExperimentResults`` into a flat metrics dict for the card.

    Per-example scores (``queue_match``, ``priority_match``, ``type_match``,
    ``label_recall_at_k``, ``reply_quality``) are read from each row's
    ``evaluation_results["results"]`` and averaged, EXCLUDING skipped rows (``score is
    None`` — our skip convention, see the D4/D6 evaluator docstrings) so a metric with
    all-skipped rows renders as "n/a" rather than a bogus 0.0 mean.

    ``ece`` and the reliability table are NOT read from ``calibration_summary``'s return
    (it only carries ``{"key": "ece", "score": <ece>}`` — LangSmith's ``EvaluationResult``
    is ``extra="forbid"``, so it can't also carry a ``reliability`` key) nor from
    LangSmith's private ``ExperimentResults._summary_results``. Instead this rebuilds the
    same ``(correct, confidence)`` pairs LOCALLY from each row's ``run.outputs`` /
    ``example.outputs`` (queue exact-match vs. the run's output confidence, skipping rows
    with no reference queue) and calls ``expected_calibration_error`` +
    ``reliability_table`` directly — the same shared source of truth used by the
    per-example evaluators and ``learn/10_calibration_demo.py``.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    skipped: set[str] = set()
    calibration_pairs: list[tuple[bool, float]] = []

    for row in results:
        eval_results = _row_field(row, "evaluation_results") or {}
        for result in eval_results.get("results", []) or []:
            key = _result_field(result, "key")
            score = _result_field(result, "score")
            if key is None:
                continue
            if isinstance(score, int | float):
                sums[key] = sums.get(key, 0.0) + float(score)
                counts[key] = counts.get(key, 0) + 1
            else:
                skipped.add(key)

        run = _row_field(row, "run")
        example = _row_field(row, "example")
        run_outputs = getattr(run, "outputs", None) or {}
        example_outputs = getattr(example, "outputs", None) or {}
        reference_queue = example_outputs.get("queue")
        if not reference_queue:
            continue
        predicted_queue = run_outputs.get("queue")
        confidence = run_outputs.get("confidence")
        if not isinstance(confidence, int | float):
            continue
        correct = (
            isinstance(predicted_queue, str)
            and predicted_queue.strip().lower() == str(reference_queue).strip().lower()
        )
        calibration_pairs.append((correct, float(confidence)))

    metrics: dict[str, Any] = {"n": n, "config": config}
    for key, total in sums.items():
        metrics[key] = total / counts[key] if counts.get(key) else None

    if calibration_pairs:
        metrics["ece"] = expected_calibration_error(calibration_pairs)
        metrics["reliability"] = reliability_table(calibration_pairs)

    if skipped:
        metrics["skipped_evaluators"] = sorted(skipped)
    return metrics


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)

    client = get_langsmith_client()
    if client is None:
        print(
            "run_experiment: no LangSmith client available (LANGSMITH_API_KEY not set). "
            "Set it in .env to run offline experiments.",
            file=sys.stderr,
        )
        return 1

    config_metadata = _apply_config(alpha=args.alpha, chat=args.chat)

    eval_settings = get_eval_settings()
    dataset_name = args.data if args.data is not None else eval_settings.dataset_name

    examples = build_eval_dataset()
    upload_dataset(examples, client=client, name=dataset_name)

    # `--limit` caps the examples actually sent through evaluate() (a cheap live smoke
    # run), independent of how many examples already live in the uploaded dataset.
    data: Any = dataset_name
    n = len(examples)
    if args.limit is not None:
        limited = list(client.list_examples(dataset_name=dataset_name, limit=args.limit))
        data = limited
        n = len(limited)

    # Deferred import: eval.target builds the live GraphAnalyzer, which requires a
    # provisioned Pinecone index / BM25 artifact; importing it eagerly at module load
    # would break offline unit tests that only import run_experiment for _apply_config
    # / _aggregate_metrics.
    from eval.target import analyze_target

    alpha = config_metadata.get("alpha")
    chat = config_metadata.get("chat")
    prefix = f"a{alpha}-{chat}"

    # mypy sees `evaluate()`'s evaluator signature as `(Run, Example | None)`, but
    # LangSmith's runtime `_normalize_run_evaluator` / `_normalize_summary_evaluator`
    # also accept our (inputs, outputs, reference_outputs) / (outputs, reference_outputs)
    # signatures by inspecting parameter names — see the D4-D6 evaluator docstrings.
    # Typed as `Any` here (rather than per-line ignores) to silence the static mismatch.
    example_evaluators: list[Any] = [
        queue_match,
        priority_match,
        type_match,
        label_recall_at_k,
        reply_quality,
    ]
    summary_evaluators: list[Any] = [calibration_summary]

    results = client.evaluate(
        analyze_target,
        data=data,
        evaluators=example_evaluators,
        summary_evaluators=summary_evaluators,
        experiment_prefix=prefix,
        metadata=config_metadata,
        max_concurrency=4,
    )

    metrics = _aggregate_metrics(results, n=n, config=config_metadata)
    json_path, md_path = write_card(metrics, prefix)
    print(f"Wrote snapshot card: {json_path} / {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
