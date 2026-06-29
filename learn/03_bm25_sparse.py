"""learn/03_bm25_sparse.py — A4: BM25 sparse vectors.

Companion to docs/learn/03-bm25-sparse.md. Run:

    uv run python learn/03_bm25_sparse.py

Proves:
  * BM25Encoder fits on a small support-ticket corpus (offline, no API key).
  * encode_query produces a sparse vector with the Pinecone-expected shape
    {"indices": list[int], "values": list[float]}.
  * Rare / specific terms (e.g. "vpn", "809") receive higher weights than
    common terms (e.g. "not", "the"), demonstrating the IDF intuition.
  * Round-trip save/load produces identical output.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Standalone scripts run from learn/, so put the project root on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.sparse import BM25SparseEncoder  # noqa: E402

# ---------------------------------------------------------------------------
# Demo corpus — short support-ticket-ish texts
# ---------------------------------------------------------------------------

CORPUS: list[str] = [
    "VPN error code 809 cannot connect to remote server",
    "Password reset link not working in email",
    "Printer offline unable to print documents",
    "Email attachment too large to send",
    "Cannot login to account after password change",
    "Network timeout connecting to VPN endpoint port 1723",
    "Unable to open PDF attachment in email client",
    "Account locked after too many failed login attempts",
    "Slow network speed affecting all devices on the floor",
    "Error 403 forbidden when accessing the internal portal",
]


def main() -> None:
    print("== A4: BM25 sparse vectors ==\n")

    # ------------------------------------------------------------------
    # 1. Fit
    # ------------------------------------------------------------------
    print(f"Corpus: {len(CORPUS)} support-ticket texts\n")
    print("Fitting BM25 on corpus...")
    encoder = BM25SparseEncoder()
    encoder.fit(CORPUS)
    print("Fit complete.\n")

    # ------------------------------------------------------------------
    # 2. Encode a keyword-heavy query
    # ------------------------------------------------------------------
    query = "VPN error code 809"
    print(f"Query: {query!r}")
    sv = encoder.encode_query(query)

    print(f"\nSparse vector — {len(sv['indices'])} non-zero dimensions:")
    print(f"  indices : {sv['indices']}")
    print(f"  values  : {[round(v, 4) for v in sv['values']]}")

    # ------------------------------------------------------------------
    # 3. Show that rare terms dominate (IDF intuition)
    # ------------------------------------------------------------------
    print("\n--- Term weight analysis ---")
    print("Encoding each query token individually to reveal its BM25 weight:\n")

    # "vpn" appears in 2/10 docs; "error" in 2/10; "code" in 1/10; "809" in 1/10
    # Common filler words that might survive tokenisation get low IDF.
    tokens = ["vpn", "error", "code", "809", "cannot", "the", "not"]
    max_label = max(len(t) for t in tokens)

    weights: dict[str, float] = {}
    for token in tokens:
        token_sv = encoder.encode_query(token)
        w = token_sv["values"][0] if token_sv["values"] else 0.0
        weights[token] = w
        label = token.rjust(max_label)
        bar = "#" * int(w * 40)
        print(f"  {label!r:>{max_label + 2}}  weight={w:.4f}  {bar}")

    print()

    # Sanity: rare/specific terms should outscore common ones.
    # "809" and "code" appear in only 1 doc each → highest IDF.
    specific = ["809", "code", "vpn"]
    common_or_absent = ["the", "not"]

    specific_weights = [weights.get(t, 0.0) for t in specific]
    common_weights = [weights.get(t, 0.0) for t in common_or_absent if weights.get(t, 0.0) > 0]

    if specific_weights and (not common_weights or min(specific_weights) >= max(common_weights)):
        print("✓  Rare/specific terms ('vpn', 'code', '809') have >= weight of common terms.")
        print("   IDF successfully down-weights terms that appear in many documents.")
    else:
        print("⚠  Weight ordering unexpected — inspect corpus size or tokenisation.")

    # ------------------------------------------------------------------
    # 4. Round-trip persistence
    # ------------------------------------------------------------------
    print("\n--- Round-trip save / load ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "bm25_params.json"

        encoder.save(artifact_path)
        print(f"Saved to: {artifact_path}")

        encoder2 = BM25SparseEncoder.load(artifact_path)
        sv2 = encoder2.encode_query(query)

        match = sv["indices"] == sv2["indices"] and sv["values"] == sv2["values"]
        status = "✓ match" if match else "✗ mismatch"
        print(f"Loaded encoder produces identical output: {status}")

    print("\nSparse vector shape: {{\"indices\": list[int], \"values\": list[float]}}")
    print("This is the exact shape Pinecone's sparse_vector field expects.")


if __name__ == "__main__":
    main()
