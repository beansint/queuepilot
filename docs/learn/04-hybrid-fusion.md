# 04 — Hybrid Fusion & Alpha Weighting

> **Learning artifact** — every task that introduces a concept ships one of these.
> Pattern: `docs/learn/_TEMPLATE.md` · Log it in `docs/final-build-plan/LEARNING-LOG.md`
> Task: `A6` · Runnable companion: `uv run python learn/04_hybrid_fusion.py`

Keep it short and concrete. Six fixed sections, always in this order.

## 1. Concept

**Hybrid search** combines a **dense** (semantic) vector and a **sparse** (lexical) vector into a
single retrieval call. Dense vectors capture meaning ("login issue" ≈ "cannot access account");
sparse vectors capture exact tokens ("error 809", "VPN port 1723"). Fusing them gets you both.

The fusion is controlled by a single scalar `alpha ∈ [0.0, 1.0]`:

```
weighted_dense[i]         = dense[i] * alpha
weighted_sparse.values[i] = sparse.values[i] * (1 - alpha)
```

- `alpha = 1.0` → **pure dense** (semantic only; sparse contribution is zero).
- `alpha = 0.0` → **pure sparse** (lexical / BM25 only; dense contribution is zero).
- `alpha = 0.5` → **balanced hybrid** (both contribute equally).

The sparse **indices** (vocabulary token IDs) are never modified — only the `values` change.

## 2. In QueuePilot

File: `app/retrieval/hybrid.py`

Two functions:

1. **`hybrid_score_norm(dense, sparse, alpha)`** — applies the alpha weighting and returns
   `(weighted_dense, weighted_sparse)` without mutating the inputs. Called in
   `analyze/baseline.py` immediately after encoding the query vectors, before the Pinecone call.

2. **`to_similar_tickets(neighbors)`** — maps the retrieval-layer `Neighbor` objects (from
   `app/retrieval/pinecone_store.py`) to the API-layer `SimilarTicket` models (from
   `app/schemas.py`). This is the boundary crossing between internal retrieval and the public
   response envelope.

Config: `app/config.py` → `hybrid_alpha: float = 0.5` (env var `HYBRID_ALPHA`). Default is
balanced. Production teams often tune alpha empirically; a higher value favours semantic recall,
a lower value favours keyword precision.

Data flow (from `docs/final-build-plan/06-ARCHITECTURE.md`):

```
text
  → dense embed (Gemini) + sparse encode (BM25)
  → hybrid_score_norm(dense, sparse, alpha)   ← this module
  → PineconeStore.hybrid_query(dense, sparse, top_k)
  → neighbors [Neighbor, ...]
  → to_similar_tickets(neighbors)             ← this module
  → AnalyzeResponse.similar_tickets
```

## 3. Why this way

**Why weight BEFORE the query?** Pinecone's `dotproduct` metric makes the combined score linear
in the individual vector components. Scaling a dense vector by `alpha` scales every dot-product
contribution by `alpha`. There is no separate "fusion step" after the query — the weighting IS
the fusion, applied at query time to the vector values.

**Why convex weighting (alpha + (1 - alpha) = 1)?** Convex combination keeps both contributions
on the same scale. If dense values are ≈ 0.0–1.0 and sparse values are ≈ 0.0–5.0, naive addition
would let sparse dominate. The (alpha, 1-alpha) pair normalises relative contribution regardless
of the raw magnitude difference between the two encoders.

**Why not fuse AFTER retrieving two separate result sets (RRF / score fusion)?** Reciprocal-rank
fusion (RRF) is an alternative that runs two independent queries and blends the ranked lists. It
requires two round trips and loses the exact-match precision of a single dotproduct computation.
Pinecone's native sparse-dense index handles both in one call.

**Why a configurable alpha (not fixed)?** The right trade-off depends on the ticket corpus and
query distribution. Error-code-heavy queues benefit from `alpha < 0.5`; free-text queues benefit
from `alpha > 0.5`. `HYBRID_ALPHA` lets operators tune without code changes.

## 4. Verify it yourself

```bash
uv run python learn/04_hybrid_fusion.py
```

**Expected output:** The script applies `hybrid_score_norm` to a small fixed dense vector and a
small fixed sparse vector at `alpha = 0.0`, `0.5`, and `1.0`. You should see:

- At `alpha=1.0`: dense values unchanged; sparse values all **0.0**.
- At `alpha=0.5`: both dense and sparse values halved.
- At `alpha=0.0`: dense values all **0.0**; sparse values unchanged.

This proves the dotproduct-linearity property: scaling the vectors before the query scales each
component's contribution proportionally.

## 5. Self-quiz

1. You have a support queue where users frequently paste exact error codes like `KERN-PANIC-0x8004`
   into tickets. Should you increase or decrease `HYBRID_ALPHA` compared to the default of 0.5?
   Why?
2. At `alpha=1.0`, the sparse vector values are all 0.0. Does this mean BM25 is broken? What
   actually happens to the sparse indices?
3. Why is it important that `hybrid_score_norm` does **not** mutate its inputs?

<details><summary>Answers</summary>

1. Decrease `HYBRID_ALPHA` (towards 0.0). A lower alpha gives more weight to the sparse (BM25)
   component, which excels at exact token matches. Error codes are rare tokens with very high IDF
   weight in BM25, so they're better served by lexical retrieval than by semantic embeddings that
   would dilute the signal across many semantically similar but lexically different terms.

2. No, BM25 is not broken. The indices (token IDs) are always preserved unchanged — only the
   values are scaled. At `alpha=1.0`, values become `0.0` but the index structure remains valid.
   A zero-valued sparse vector simply contributes nothing to the dotproduct score, which is the
   intended behaviour for pure-dense mode.

3. The same encoded vectors may be used in multiple contexts (retries, logging, batching) or
   passed in from a caller that expects them unchanged. Mutating inputs is a hidden side-effect
   that causes subtle, hard-to-trace bugs. The function creates new lists instead, guaranteeing
   referential transparency.

</details>

## 6. Takeaway

Hybrid search fuses dense (semantic) and sparse (lexical) vectors by scaling them with alpha and
(1 - alpha) before the Pinecone query; because the index uses dotproduct, this scaling directly
controls each component's contribution to the final relevance score.
