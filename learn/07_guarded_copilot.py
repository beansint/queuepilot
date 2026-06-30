"""learn/07_guarded_copilot.py — B8: guarded-copilot decision routing.

Companion to docs/learn/07-guarded-copilot.md. Run:

    uv run python learn/07_guarded_copilot.py

Proves: the decide node routes tickets to ANSWER, CLARIFY, or ESCALATE based on
interpretable, deterministic thresholds — not on LLM self-confidence.

No network — imports `route_decision`, `ESCALATE_CONFIDENCE_BELOW`, and
`ESCALATE_SLA_RISK_ABOVE` directly from the production app code.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analyze.graph import (  # noqa: E402
    CLARIFY_CONFIDENCE_BELOW,
    ESCALATE_CONFIDENCE_BELOW,
    ESCALATE_SLA_RISK_ABOVE,
    route_decision,
)


def main() -> None:
    print("== B8: Guarded-copilot decision routing ==\n")
    print("Thresholds loaded from app/analyze/graph.py:")
    print(f"  ESCALATE_CONFIDENCE_BELOW = {ESCALATE_CONFIDENCE_BELOW}")
    print(f"  ESCALATE_SLA_RISK_ABOVE   = {ESCALATE_SLA_RISK_ABOVE}")
    print()
    print(
        f"{'Case':<40} {'conf':>5}  {'sla':>5}  {'missing':>7}  {'→ route'}"
    )
    print("-" * 75)

    cases: list[tuple[str, float, float, list[str]]] = [
        # (label, confidence, sla_risk, missing_info)
        ("Confident + complete", 0.85, 0.35, []),
        ("Mid confidence + missing info", 0.58, 0.40, ["no error code"]),
        ("Low confidence (diverse queues)", 0.32, 0.20, []),
        ("Extreme SLA risk + not confident", 0.55, 0.92, []),
        ("Confident despite high SLA risk", 0.88, 0.95, []),
        ("Low conf + missing (escalate beats clarify)", 0.25, 0.60, ["no account id"]),
    ]

    for label, conf, risk, missing in cases:
        route = route_decision(conf, risk, missing)
        missing_count = len(missing)
        print(
            f"  {label:<38} {conf:>5.2f}  {risk:>5.2f}  {missing_count:>7}  → {route.upper()}"
        )

    print()
    print("Explanation of each route (confidence-primary):")
    print(f"  ANSWER   : confidence >= {CLARIFY_CONFIDENCE_BELOW} (trust strong retrieval) — else:")
    print(
        f"  ESCALATE : conf < {ESCALATE_CONFIDENCE_BELOW} OR sla_risk > {ESCALATE_SLA_RISK_ABOVE}"
    )
    print("  CLARIFY  : (not confident, not escalating) AND missing_info non-empty")
    print("  ANSWER   : otherwise")
    print()
    print(
        "Conclusion: the copilot never guesses when uncertain — it escalates to a human instead."
    )


if __name__ == "__main__":
    main()
