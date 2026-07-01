"""learn/10_calibration_demo.py — why we DON'T trust an LLM's self-reported confidence.

Run standalone:  uv run python learn/10_calibration_demo.py

Companion doc: docs/learn/10-rag-to-guarded-copilot.md

Proves (offline, no network, no LLM):
  A model can be OVERCONFIDENT — it claims ~95% sure on every answer while actually
  being right far less often. That "self-confidence" is nearly useless for deciding
  when to trust the system. QueuePilot instead BLENDS observable signals (neighbor
  agreement, retrieval closeness, missing-info penalty) into a score that actually
  tracks correctness. This script simulates both and measures how well each is
  *calibrated* — i.e. whether "70% confident" really means "right ~70% of the time".

It imports the REAL production function `full_confidence_breakdown` from app code, so
the "blended" number here is exactly what /analyze?explain=true shows you.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analyze.scoring import full_confidence_breakdown  # noqa: E402

# Deterministic so the lesson is reproducible run-to-run.
RNG = random.Random(7)
N_TICKETS = 600


def _simulate() -> list[tuple[bool, float, float]]:
    """Return (was_correct, self_reported_confidence, blended_confidence) per ticket.

    Each ticket has two OBSERVABLE retrieval signals — how strongly the nearest
    neighbours agree, and how close the top match is — plus whether details were
    missing. We let the *true* chance the answer is correct depend on those same
    signals (strong agreement + a close match => more likely correct). That is the
    whole point: the blended score is built from signals that genuinely predict
    correctness, whereas the LLM's self-confidence is not.
    """
    rows: list[tuple[bool, float, float]] = []
    for _ in range(N_TICKETS):
        agreement = RNG.choice([0.2, 0.4, 0.6, 0.8, 1.0])  # fraction of neighbours agreeing
        top_score = RNG.uniform(0.2, 0.85)                 # closeness of the best match
        missing = RNG.random() < 0.30                      # were key details absent?

        # Ground truth: probability the retrieval-majority answer is actually right.
        p_correct = 0.30 + 0.45 * agreement + 0.25 * (top_score - 0.5) - (0.12 if missing else 0.0)
        p_correct = max(0.0, min(1.0, p_correct))
        was_correct = RNG.random() < p_correct

        # (a) The overconfident LLM: claims ~0.95 on every single ticket.
        self_conf = 0.95

        # (b) Our blended confidence — the REAL production formula.
        # llm_queue == majority_queue here (consistent) so the +consistency term applies.
        blended = full_confidence_breakdown(
            top_score=top_score,
            agreement=agreement,
            llm_queue="tech-support",
            majority_queue="tech-support",
            missing_count=1 if missing else 0,
        )["final"]

        rows.append((was_correct, self_conf, blended))
    return rows


def _bar(frac: float, width: int = 24) -> str:
    filled = round(frac * width)
    return "█" * filled + "·" * (width - filled)


def _reliability(rows: list[tuple[bool, float, float]], pick: str) -> None:
    """Print a calibration/reliability table: within each confidence bucket, what
    fraction were actually correct? Perfect calibration => accuracy ≈ bucket midpoint."""
    buckets = [(0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 1.01)]
    header = f"  {'confidence bucket':>18} │ {'n':>4} │ {'claimed':>8} │ {'ACTUAL acc':>10} │ reliability"
    print(header)
    print("  " + "─" * 74)
    gaps: list[float] = []
    for lo, hi in buckets:
        sel = [c for (c, s, b) in rows if lo <= (s if pick == "self" else b) < hi]
        if not sel:
            continue
        acc = sum(sel) / len(sel)
        mid = min((lo + hi) / 2, 1.0)
        gaps.append(abs(mid - acc) * len(sel))
        print(f"  {f'{lo:.2f}–{hi if hi <= 1 else 1.00:.2f}':>18} │ {len(sel):>4} │ "
              f"{mid:>8.2f} │ {acc:>10.2f} │ {_bar(acc)}")
    total = len(rows)
    ece = sum(gaps) / total if total else 0.0
    print(f"  → calibration error (lower = more trustworthy): {ece:.3f}")


def main() -> None:
    print("== Why we don't trust an LLM's self-reported confidence ==\n")
    rows = _simulate()
    overall_acc = sum(c for c, _, _ in rows) / len(rows)

    print(f"Simulated {len(rows)} tickets. The system was actually correct "
          f"{overall_acc*100:.0f}% of the time.\n")

    print("(a) LLM SELF-CONFIDENCE — it claims 0.95 on every ticket:")
    print(f"    claims 95% sure, but is right only {overall_acc*100:.0f}% of the time "
          f"→ overconfident & USELESS for routing.")
    _reliability(rows, "self")

    print("\n(b) BLENDED CONFIDENCE — built from agreement + closeness − missing "
          "(the real full_confidence_breakdown):")
    _reliability(rows, "blended")

    print("\nTakeaway: the blended score's buckets line up with real accuracy "
          "(low error), so\n'70% confident' actually means 'right ~70% of the time'. "
          "That is what lets QueuePilot\nroute answer / clarify / escalate honestly — "
          "and it never asked the LLM how sure it was.")


if __name__ == "__main__":
    main()
