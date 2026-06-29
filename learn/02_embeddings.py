"""learn/02_embeddings.py — A3: Gemini embeddings with fixed 768-dim Matryoshka output.

Companion to docs/learn/02-embeddings.md. Run:

    uv run python learn/02_embeddings.py

Proves:
  * Real Gemini API call succeeds with gemini-embedding-001.
  * Every returned vector has exactly 768 floats (EMBED_DIM pinned at A3).
  * Cosine similarity is higher for semantically similar texts than for unrelated texts,
    demonstrating that embeddings encode meaning rather than surface word overlap.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.providers.embeddings import EMBED_DIM, GeminiEmbedder, get_embedder  # noqa: E402, I001


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def cosine_sim(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def main() -> None:
    print("== A3: Gemini embeddings ==\n")
    print("Model : gemini-embedding-001")
    print(f"Dim   : {EMBED_DIM}\n")

    # Two semantically similar texts, one unrelated text.
    texts = [
        "My printer is offline and won't connect.",            # A — printer problem
        "The printer stopped working and I can't print anything.",  # B — printer problem
        "I need help booking a flight to Tokyo.",              # C — travel inquiry
    ]
    labels = ["A", "B", "C"]
    descriptions = [
        "printer offline",
        "printer stopped working",
        "flight booking",
    ]

    for label, text, desc in zip(labels, texts, descriptions, strict=True):
        print(f"Text {label} ({desc!r}):")
        print(f"  {text!r}")
    print()

    # Obtain embedder — raises RuntimeError if GEMINI_API_KEY is unset.
    embedder: GeminiEmbedder  # type annotation for mypy
    raw = get_embedder()
    if not isinstance(raw, GeminiEmbedder):
        raise RuntimeError("Expected GeminiEmbedder from get_embedder()")
    embedder = raw

    # Embed all three as documents in a single batched call.
    vectors = embedder.embed_documents(texts)

    print("Vector lengths (must all be 768):")
    for label, vec in zip(labels, vectors, strict=True):
        status = "✓" if len(vec) == EMBED_DIM else f"✗ got {len(vec)}"
        print(f"  Vector {label}: {len(vec)}  {status}")
    print()

    # Also prove embed_query works and returns the same dimension.
    query_vec = embedder.embed_query(texts[0])
    q_status = "✓" if len(query_vec) == EMBED_DIM else f"✗ got {len(query_vec)}"
    print(f"embed_query length (must be 768): {len(query_vec)}  {q_status}\n")

    # Pairwise cosine similarities.
    vec_a, vec_b, vec_c = vectors[0], vectors[1], vectors[2]
    sim_ab = cosine_sim(vec_a, vec_b)
    sim_ac = cosine_sim(vec_a, vec_c)
    sim_bc = cosine_sim(vec_b, vec_c)

    print("Pairwise cosine similarities:")
    print(f"  A vs B (same topic — printer):     {sim_ab:.4f}  ← should be HIGH")
    print(f"  A vs C (different topic — travel): {sim_ac:.4f}  ← should be lower")
    print(f"  B vs C (different topic — travel): {sim_bc:.4f}  ← should be lower")
    print()

    if sim_ab > sim_ac and sim_ab > sim_bc:
        print("✓  Similar texts (A, B) score higher than unrelated (A/C, B/C).")
        print("   Embeddings encode meaning, not just word overlap.")
    else:
        print("⚠  Similarity ordering unexpected — check model or texts.")


if __name__ == "__main__":
    main()
