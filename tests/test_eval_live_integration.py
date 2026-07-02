"""D — LIVE integration test: the eval stack end-to-end against the live pipeline.

Skipped by default. Run explicitly with:

    QUEUEPILOT_RUN_INTEGRATION=1 uv run pytest -m integration -k eval_live_integration

PREREQUISITES:
  - The ingest pipeline (uv run python data/ingest.py) must have populated the
    Pinecone index and written data/artifacts/bm25_params.json.
  - All required API keys must be present in .env (VOYAGE_API_KEY, PINECONE_API_KEY,
    GROQ_API_KEY for the default chat model; GEMINI_API_KEY optional, enables the
    reply-quality judge assertion below).

This test is deliberately small (2 held-out examples) and self-contained: it exercises
``analyze_target`` -> the deterministic evaluators -> calibration -> (optionally) the
LLM judge directly, WITHOUT going through LangSmith's hosted ``evaluate()``, so it still
works even if the eval dataset has never been uploaded to LangSmith.

DO NOT run this test during offline development. Opus runs it after verifying that the
live index and artifact are available.
"""

from __future__ import annotations

import os

import pytest

from app.config import get_settings
from eval.dataset import build_eval_dataset
from eval.evaluators.calibration import expected_calibration_error
from eval.evaluators.deterministic import label_recall_at_k, priority_match, queue_match
from eval.evaluators.judge import reply_quality
from eval.target import analyze_target

pytestmark = pytest.mark.integration

_RUN: bool = os.environ.get("QUEUEPILOT_RUN_INTEGRATION") == "1"


@pytest.mark.skipif(
    not _RUN,
    reason="set QUEUEPILOT_RUN_INTEGRATION=1 to run the live eval integration test",
)
def test_eval_stack_live_end_to_end() -> None:
    """Real ``analyze_target`` + real evaluators, run over a couple of held-out tickets."""
    examples = build_eval_dataset()
    held_out = [ex for ex in examples if ex.source != "edge"]
    assert len(held_out) >= 2, "expected at least 2 held-out (non-edge) eval examples"
    sample = held_out[:2]

    pairs: list[tuple[bool, float]] = []
    any_similar_tickets = False

    for example in sample:
        outputs = analyze_target(example.inputs)
        reference_outputs = example.outputs

        for evaluator in (queue_match, priority_match, label_recall_at_k):
            result = evaluator(example.inputs, outputs, reference_outputs)
            # Evaluators never return bare None (LangSmith's evaluate() rejects that) --
            # a skip is a dict with score=None instead.
            assert isinstance(result, dict) and result.get("score") in (0.0, 1.0, None), (
                f"{evaluator.__name__} returned an unexpected shape: {result!r}"
            )

        reference_queue = reference_outputs.get("queue")
        predicted_queue = outputs.get("queue")
        if reference_queue:
            correct = (
                isinstance(predicted_queue, str)
                and predicted_queue.strip().lower() == str(reference_queue).strip().lower()
            )
            confidence = outputs.get("confidence")
            assert isinstance(confidence, int | float), (
                f"expected a numeric confidence, got: {confidence!r}"
            )
            pairs.append((correct, float(confidence)))

        similar_tickets = outputs.get("similar_tickets") or []
        if similar_tickets:
            any_similar_tickets = True

        if get_settings().gemini_api_key and outputs.get("suggested_reply"):
            judge_result = reply_quality(example.inputs, outputs, reference_outputs)
            judge_score = judge_result.get("score") if isinstance(judge_result, dict) else None
            assert isinstance(judge_result, dict) and (
                judge_score is None or 0.0 <= judge_score <= 1.0
            ), f"reply_quality returned an unexpected shape: {judge_result!r}"

    ece = expected_calibration_error(pairs)
    assert isinstance(ece, float)
    assert 0.0 <= ece <= 1.0, f"ECE out of range: {ece}"

    assert any_similar_tickets, (
        "expected at least one example to produce a non-empty similar_tickets list, "
        "proving retrieval ran against the live Pinecone index"
    )
