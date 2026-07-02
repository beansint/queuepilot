"""learn/11_eval.py — D11: offline vs online eval.

Companion to docs/learn/11-eval.md. Run:

    uv run python learn/11_eval.py

Proves two distinct evaluation modes with the REAL deterministic evaluators
(eval.evaluators.deterministic) but a MOCK target — no network, no LLM, no LangSmith:

  1. Offline eval — a fixed target run over a small curated dataset with known
     reference labels, scored with queue_match / priority_match / type_match /
     label_recall_at_k. Reproducible: same inputs -> same scores, every time.
  2. Online eval — a simulated stream of production "thumbs" feedback (the kind
     POST /feedback records via app/feedback.py), aggregated into a satisfaction
     rate. No reference labels here — just real users grading real outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.evaluators.deterministic import (  # noqa: E402
    label_recall_at_k,
    priority_match,
    queue_match,
    type_match,
)

# ---------------------------------------------------------------------------
# 1. Offline eval: a fixed dataset (inputs + reference_outputs) + a mock target.
# ---------------------------------------------------------------------------

#: A tiny curated dataset, shaped like eval.dataset.EvalExample rows.
FIXTURE_EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "fx-1",
        "inputs": {"text": "My card was charged twice for the same order."},
        "reference_outputs": {"queue": "Billing", "priority": "high", "type": "Incident"},
    },
    {
        "id": "fx-2",
        "inputs": {"text": "How do I reset my password?"},
        "reference_outputs": {"queue": "Account", "priority": "low", "type": "Request"},
    },
    {
        "id": "fx-3",
        "inputs": {"text": "The mobile app crashes on launch since the last update."},
        "reference_outputs": {"queue": "Technical Support", "priority": "high", "type": "Incident"},
    },
]


def mock_target(inputs: dict[str, Any]) -> dict[str, Any]:
    """A canned, deterministic stand-in for ``GraphAnalyzer.analyze`` (eval/target.py).

    A real offline run points this at the real pipeline; here we hardcode plausible
    outputs per fixture id so the evaluators have something concrete to score,
    including one intentional miss (fx-3's queue) to show a 0.0 score in the mix.
    """
    canned: dict[str, dict[str, Any]] = {
        "fx-1": {
            "queue": "Billing",
            "priority": "high",
            "type": "Incident",
            "confidence": 0.88,
            "similar_tickets": [{"queue": "Billing"}, {"queue": "Billing"}],
        },
        "fx-2": {
            "queue": "Account",
            "priority": "low",
            "type": "Request",
            "confidence": 0.91,
            "similar_tickets": [{"queue": "Account"}],
        },
        "fx-3": {
            # Intentional miss: pipeline said Billing, reference says Technical Support.
            "queue": "Billing",
            "priority": "high",
            "type": "Incident",
            "confidence": 0.52,
            "similar_tickets": [{"queue": "Billing"}, {"queue": "Technical Support"}],
        },
    }
    return canned[inputs["_id"]]


def run_offline_eval() -> None:
    print("== Offline eval ==\n")
    print(
        "Fixed target (mock_target) run over a curated dataset with known reference\n"
        "labels, scored by the REAL evaluators from eval.evaluators.deterministic.\n"
        "This is reproducible: rerun it and you get the exact same numbers.\n"
    )

    evaluators = [queue_match, priority_match, type_match, label_recall_at_k]
    totals: dict[str, list[float]] = {ev.__name__: [] for ev in evaluators}

    for example in FIXTURE_EXAMPLES:
        inputs = {**example["inputs"], "_id": example["id"]}
        reference_outputs = example["reference_outputs"]
        outputs = mock_target(inputs)

        print(f"-- {example['id']}: {example['inputs']['text']!r}")
        for evaluator in evaluators:
            # Evaluators never return None (LangSmith's evaluate() rejects a bare None
            # return) — a "skip" (no reference label) is a dict with score=None instead.
            result = evaluator(inputs, outputs, reference_outputs)
            score = result["score"]
            if score is None:
                print(f"   {evaluator.__name__:<20} skipped ({result.get('comment')})")
                continue
            totals[evaluator.__name__].append(score)
            print(f"   {evaluator.__name__:<20} = {score}")

    print("\n-- Aggregate (offline) --")
    for name, scores in totals.items():
        if not scores:
            continue
        mean = sum(scores) / len(scores)
        print(f"  {name:<20} mean = {mean:.3f}  (n={len(scores)})")


# ---------------------------------------------------------------------------
# 2. Online eval: simulated production feedback (thumbs), aggregated.
# ---------------------------------------------------------------------------

#: Each row is (ticket_id, thumbs_up, was_actually_correct) — the kind of signal
#: POST /feedback records via app.feedback.submit_feedback: a human grading a REAL
#: production output, with no dataset or reference labels involved at grading time.
ONLINE_FEEDBACK: list[tuple[str, bool, bool]] = [
    ("run-101", True, True),
    ("run-102", True, True),
    ("run-103", False, False),
    ("run-104", True, False),  # user thumbs-up'd a reply that was later corrected
    ("run-105", True, True),
    ("run-106", False, False),
    ("run-107", True, True),
]


def run_online_eval() -> None:
    print("\n== Online eval ==\n")
    print(
        "No dataset, no reference labels — real users grading real production traces\n"
        "(the POST /feedback flywheel in app/feedback.py). We aggregate satisfaction\n"
        "(thumbs) and, separately, how often 'thumbs up' actually agreed with ground\n"
        "truth once corrections came in — that gap is exactly what offline eval cannot see.\n"
    )

    n = len(ONLINE_FEEDBACK)
    thumbs_up = sum(1 for _, up, _ in ONLINE_FEEDBACK if up)
    satisfaction_rate = thumbs_up / n

    correct = sum(1 for _, _, ok in ONLINE_FEEDBACK if ok)
    true_accuracy = correct / n

    thumbs_up_but_wrong = sum(1 for _, up, ok in ONLINE_FEEDBACK if up and not ok)

    for run_id, up, ok in ONLINE_FEEDBACK:
        print(f"  {run_id}: thumbs={'up' if up else 'down':<4} correct={ok}")

    print(f"\n  satisfaction_rate (thumbs-up / n) = {thumbs_up}/{n} = {satisfaction_rate:.3f}")
    print(f"  true_accuracy (correct / n)       = {correct}/{n} = {true_accuracy:.3f}")
    print(
        f"  thumbs-up-but-wrong               = {thumbs_up_but_wrong}/{n} "
        "-> users don't always notice a wrong label; corrections are what close this gap"
    )


def main() -> None:
    print("== D11: Offline vs online eval ==\n")
    run_offline_eval()
    run_online_eval()

    print(
        "\nTakeaway: offline eval is reproducible and pre-deploy (fixed target + fixed\n"
        "dataset + deterministic evaluators -> the same scores every run); online eval is\n"
        "post-deploy and reflects the real traffic distribution + human judgment, but it's\n"
        "noisier and can disagree with ground truth (see thumbs-up-but-wrong above) — which\n"
        "is exactly why QueuePilot runs both (eval/run_experiment.py + eval/run_online.py)\n"
        "and feeds corrections from POST /feedback back into future eval datasets."
    )


if __name__ == "__main__":
    main()
