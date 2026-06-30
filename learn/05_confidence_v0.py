"""learn/05_confidence_v0.py — A8: Blended confidence v0 (retrieval-only).

Companion to docs/learn/05-confidence-v0.md. Run:

    uv run python learn/05_confidence_v0.py

Proves:
  * majority_vote derives queue, priority, type and the agreement fraction from a
    list of Neighbor objects — pure, no I/O.
  * confidence_v0 blends agreement + sigmoid(top_score) into a number in [0, 1].
  * HIGH label agreement + STRONG score → high confidence (~0.88).
  * DIVIDED labels + WEAK score → low confidence (~0.36).
  * Even pathological inputs (agreement=1.0, score=1000) are clamped to [0.0, 1.0].
  * EMPTY neighbor list → confidence of 0.0 (safe fallback).

No network. No API keys. Runs offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Standalone scripts run from learn/, so put the project root on sys.path for `import app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analyze.baseline import confidence_v0, majority_vote  # noqa: E402, I001
from app.retrieval.pinecone_store import Neighbor  # noqa: E402


# ---------------------------------------------------------------------------
# Scenario builder
# ---------------------------------------------------------------------------


def _run_scenario(label: str, neighbors: list[Neighbor]) -> None:
    """Print a full majority-vote + confidence_v0 walkthrough for *neighbors*."""
    print(f"--- {label} ---")

    queue, priority, category, agreement = majority_vote(neighbors)
    print(f"  neighbors  : {len(neighbors)}")
    print(f"  queues     : {[n.queue for n in neighbors]}")
    print(f"  → winner   : queue={queue!r}  priority={priority!r}  category={category!r}")
    pct = f"{agreement * 100:.0f}%"
    print(f"  agreement  : {agreement:.2f}  ({pct} of neighbors match winning queue)")

    if neighbors:
        top_score = neighbors[0].score
        conf = confidence_v0(top_score=top_score, agreement=agreement)
        print(f"  top_score  : {top_score}")
        print(f"  confidence : {conf:.4f}  (blended)")
    else:
        conf = 0.0
        print(f"  confidence : {conf:.4f}  (no neighbors → safe fallback)")

    print()


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def main() -> None:
    print("== A8: Blended Confidence v0 (retrieval-only, no LLM) ==\n")
    print(
        "Formula: confidence = clamp([0,1],  0.6 * agreement  +  0.4 * sigmoid(top_score))\n"
    )

    # ----------------------------------------------------------------
    # Scenario 1 — high confidence
    #   All five neighbors agree on "IT Support" + strong top-score.
    # ----------------------------------------------------------------
    high_neighbors: list[Neighbor] = [
        Neighbor(score=0.90, queue="IT Support", priority="high",
                 type="vpn", snippet="VPN error"),
        Neighbor(score=0.85, queue="IT Support", priority="high",
                 type="vpn", snippet="VPN timeout"),
        Neighbor(score=0.80, queue="IT Support", priority="medium",
                 type="vpn", snippet="VPN client crash"),
        Neighbor(score=0.75, queue="IT Support", priority="high",
                 type="network", snippet="Remote access fails"),
        Neighbor(score=0.70, queue="IT Support", priority="low",
                 type="vpn", snippet="VPN install issue"),
    ]
    _run_scenario(
        "SCENARIO 1 — High confidence (unanimous + strong score)", high_neighbors
    )

    # ----------------------------------------------------------------
    # Scenario 2 — low confidence
    #   Neighbors split across four queues + weak top-score.
    # ----------------------------------------------------------------
    low_neighbors: list[Neighbor] = [
        Neighbor(score=0.10, queue="IT Support", priority="high",
                 type="vpn", snippet="Connectivity"),
        Neighbor(score=0.09, queue="Billing",    priority="low",
                 type="charge", snippet="Invoice"),
        Neighbor(score=0.08, queue="Security",   priority="high",
                 type="threat", snippet="Phishing"),
        Neighbor(score=0.07, queue="Identity",   priority="medium",
                 type="access", snippet="Password reset"),
    ]
    _run_scenario(
        "SCENARIO 2 — Low confidence (divided labels + weak score)", low_neighbors
    )

    # ----------------------------------------------------------------
    # Scenario 3 — empty neighbors (safe fallback)
    # ----------------------------------------------------------------
    _run_scenario("SCENARIO 3 — Empty neighbors (safe fallback → 0.0)", [])

    # ----------------------------------------------------------------
    # Scenario 4 — clamp verification
    #   Pathological inputs must never escape [0.0, 1.0].
    # ----------------------------------------------------------------
    print("--- CLAMP VERIFICATION ---")
    upper = confidence_v0(top_score=1000.0, agreement=1.0)
    lower = confidence_v0(top_score=-1000.0, agreement=0.0)
    print(f"  score=1000, agreement=1.0  → confidence = {upper:.6f}  (should be ≤ 1.0)")
    print(f"  score=-1000, agreement=0.0 → confidence = {lower:.6f}  (should be ≥ 0.0)")
    assert upper <= 1.0, f"upper clamp failed: {upper}"
    assert lower >= 0.0, f"lower clamp failed: {lower}"
    print()

    # ----------------------------------------------------------------
    # Validate monotonicity (sanity check)
    # ----------------------------------------------------------------
    print("--- MONOTONICITY CHECK ---")
    weak   = confidence_v0(top_score=0.0, agreement=0.2)
    strong = confidence_v0(top_score=1.0, agreement=0.9)
    print(f"  weak  (score=0.0, agreement=0.2): {weak:.4f}")
    print(f"  strong(score=1.0, agreement=0.9): {strong:.4f}")
    assert strong > weak, "monotonicity violated"
    print()

    print("All checks passed. Confidence v0 is well-behaved across all scenarios.")


if __name__ == "__main__":
    main()
