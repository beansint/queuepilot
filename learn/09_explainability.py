"""learn/09_explainability.py — C8: in-app explainability (?explain=true).

Companion to docs/learn/09-explainability.md. Run:

    uv run python learn/09_explainability.py

Proves: `full_confidence_breakdown` and `sla_risk_breakdown` — the REAL production
functions the `score` node calls (app/analyze/graph.py) — decompose the confidence
and SLA-risk scores into interpretable, weighted terms that sum exactly to the final
value. No network, no LLM, no LangSmith — this is the deterministic half of the
guarded-copilot pipeline (see also learn/07_guarded_copilot.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analyze.scoring import (  # noqa: E402
    full_confidence_breakdown,
    sla_risk_breakdown,
)


def main() -> None:
    print("== C8: In-app explainability (?explain=true) ==\n")

    # ------------------------------------------------------------------
    # A worked example: a ticket where retrieval strongly agrees, the LLM's
    # queue disagrees with the majority vote, and one detail is missing.
    # ------------------------------------------------------------------
    top_score = 0.62
    agreement = 1.0
    llm_queue = "billing"
    majority_queue = "refunds"
    missing_count = 1

    print("-- Confidence breakdown (full_confidence_breakdown) --")
    print(
        f"  inputs: top_score={top_score}, agreement={agreement}, "
        f"llm_queue={llm_queue!r}, majority_queue={majority_queue!r}, "
        f"missing_count={missing_count}\n"
    )

    conf = full_confidence_breakdown(
        top_score, agreement, llm_queue, majority_queue, missing_count
    )
    for key, value in conf.items():
        print(f"  {key:<20} = {value}")

    computed = (
        conf["w_agreement"] * conf["agreement"]
        + conf["w_score"] * conf["sigmoid_top_score"]
        + conf["consistency"]
        - conf["penalty"]
    )
    computed_clamped = max(0.0, min(1.0, computed))
    print(
        f"\n  reassembled: {conf['w_agreement']}*{conf['agreement']} "
        f"+ {conf['w_score']}*{conf['sigmoid_top_score']:.4f} "
        f"+ {conf['consistency']} - {conf['penalty']} "
        f"= {computed:.4f}  (clamped -> {computed_clamped:.4f})"
    )
    assert computed_clamped == conf["final"], "breakdown terms must sum to `final`"
    print(f"  matches conf['final'] = {conf['final']}  -> PROVEN\n")
    print(
        "  Note: consistency = 0.0 because llm_queue "
        f"({llm_queue!r}) != majority_queue ({majority_queue!r}) — the +{conf['w_consistency']} "
        "bonus was withheld. This is the exact 'why' a human sees under ?explain=true."
    )

    # ------------------------------------------------------------------
    # SLA-risk breakdown for the same ticket.
    # ------------------------------------------------------------------
    priority = "high"
    frustration = 0.7
    has_missing = missing_count > 0

    print("\n-- SLA-risk breakdown (sla_risk_breakdown) --")
    print(
        f"  inputs: priority={priority!r}, frustration={frustration}, has_missing={has_missing}\n"
    )

    sla = sla_risk_breakdown(priority, frustration, has_missing)
    for key, value in sla.items():
        print(f"  {key:<20} = {value}")

    sla_computed = (
        sla["w_priority"] * sla["priority_weight"]
        + sla["w_frustration"] * sla["frustration"]
        + sla["w_missing"] * (1.0 if sla["has_missing"] else 0.0)
    )
    sla_computed_clamped = max(0.0, min(1.0, sla_computed))
    print(
        f"\n  reassembled: {sla['w_priority']}*{sla['priority_weight']} "
        f"+ {sla['w_frustration']}*{sla['frustration']} "
        f"+ {sla['w_missing']}*{1.0 if sla['has_missing'] else 0.0} "
        f"= {sla_computed:.4f}  (clamped -> {sla_computed_clamped:.4f})"
    )
    assert sla_computed_clamped == sla["final"], "breakdown terms must sum to `final`"
    print(f"  matches sla['final'] = {sla['final']}  -> PROVEN")

    # ------------------------------------------------------------------
    # This is exactly what AnalyzeResponse.debug["confidence_breakdown"] /
    # ["sla_breakdown"] contain when a caller hits POST /analyze?explain=true —
    # GraphAnalyzer._build_debug copies these dicts verbatim off TicketState.
    # ------------------------------------------------------------------
    print(
        "\nConclusion: every term behind `confidence` and `sla_risk` is inspectable and "
        "sums exactly to the final score — this is what ?explain=true exposes via "
        "AnalyzeResponse.debug, computed with zero LLM calls and zero LangSmith dependency."
    )


if __name__ == "__main__":
    main()
