"""learn/04_hybrid_fusion.py — A6: Hybrid fusion & alpha weighting.

Companion to docs/learn/04-hybrid-fusion.md. Run:

    uv run python learn/04_hybrid_fusion.py

Proves:
  * hybrid_score_norm scales dense by alpha and sparse values by (1 - alpha).
  * alpha=1.0 → dense unchanged, sparse values ALL ZERO (pure semantic).
  * alpha=0.5 → both halved (balanced hybrid).
  * alpha=0.0 → dense ALL ZERO, sparse values unchanged (pure lexical).
  * Sparse indices are NEVER modified — only values change.
  * Inputs are not mutated (original vectors are printed unchanged after the call).

No network. No API keys. Runs offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Standalone scripts run from learn/, so put the project root on sys.path for `import app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.hybrid import hybrid_score_norm  # noqa: E402, I001
from app.retrieval.sparse import SparseVector  # noqa: E402


# ---------------------------------------------------------------------------
# Tiny fixed example vectors (no network, no API key required)
# ---------------------------------------------------------------------------

#: A minimal 4-dim dense vector (imagine this came from Gemini).
DENSE: list[float] = [0.2, 0.4, 0.6, 0.8]

#: A minimal sparse vector with 3 non-zero dimensions (imagine this came from BM25).
SPARSE: SparseVector = {
    "indices": [101, 205, 999],   # vocabulary token IDs — never change
    "values":  [1.0, 2.0, 0.5],  # BM25 weights for those tokens
}


def _fmt_floats(values: list[float]) -> str:
    return "[" + ", ".join(f"{v:.3f}" for v in values) + "]"


def main() -> None:
    print("== A6: Hybrid Fusion & Alpha Weighting ==\n")
    print("Original dense vector : ", _fmt_floats(DENSE))
    print("Original sparse values:", _fmt_floats(SPARSE["values"]))
    print("Original sparse indices:", SPARSE["indices"])
    print()

    for alpha in (0.0, 0.5, 1.0):
        weighted_dense, weighted_sparse = hybrid_score_norm(DENSE, SPARSE, alpha=alpha)

        print(f"--- alpha = {alpha} ---")
        print(f"  dense  (×{alpha})      : {_fmt_floats(weighted_dense)}")
        print(f"  sparse values (×{1-alpha}) : {_fmt_floats(weighted_sparse['values'])}")
        print(f"  sparse indices (unchanged): {weighted_sparse['indices']}")

        # Illustrative descriptions
        if alpha == 1.0:
            print("  → Pure dense: sparse values are all 0.000 — BM25 contributes nothing.")
        elif alpha == 0.0:
            print("  → Pure sparse: dense values are all 0.000 — embeddings contribute nothing.")
        else:
            print("  → Balanced: both components contribute equally.")
        print()

    # ------------------------------------------------------------------
    # Prove inputs were NOT mutated
    # ------------------------------------------------------------------
    print("--- Immutability check ---")
    dense_copy = list(DENSE)
    sparse_copy: SparseVector = {
        "indices": list(SPARSE["indices"]),
        "values": list(SPARSE["values"]),
    }
    hybrid_score_norm(dense_copy, sparse_copy, alpha=0.5)

    dense_ok = dense_copy == DENSE
    sparse_ok = sparse_copy["values"] == SPARSE["values"]
    print(f"  dense  unchanged after call: {'✓' if dense_ok else '✗'}")
    print(f"  sparse unchanged after call: {'✓' if sparse_ok else '✗'}")

    if dense_ok and sparse_ok:
        print("\nAll checks passed. Alpha weighting is correct and inputs are never mutated.")
    else:
        print("\n✗ Mutation detected — check hybrid_score_norm implementation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
