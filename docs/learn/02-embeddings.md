# 02 — Embeddings & Dimensions

> **Learning artifact** — every task that introduces a concept ships one of these.
> Pattern: `docs/learn/_TEMPLATE.md` · Log it in `docs/final-build-plan/LEARNING-LOG.md`
> Task: `A3` · Runnable companion: `uv run python learn/02_embeddings.py`

Keep it short and concrete. Six fixed sections, always in this order.

## 1. Concept

An **embedding** is a fixed-length vector of floats that encodes the *meaning* of a piece of text.
Two texts with similar meanings end up with vectors that point in roughly the same direction in that
high-dimensional space — even if they share no words in common.

A **dimension** is the length of that vector (e.g. 768 floats).  All vectors in a vector database
index must have the same dimension; mixing lengths is a hard schema error.

**Matryoshka Representation Learning (MRL)** trains a single embedding model such that its first
*N* dimensions (any N from 1 to the full dim) already capture a useful embedding.  This means you
can trade off index size vs. quality by choosing `output_dimensionality` at embedding time.  We fix
ours at **768** for a good accuracy / storage balance.

**Cosine similarity** measures the angle between two vectors (1.0 = identical direction, 0.0 =
orthogonal, −1.0 = opposite).  It is the standard metric when vectors may be scale-normalized.

**Dot-product** is cosine similarity × magnitude product.  Pinecone hybrid indexes require
`metric="dotproduct"` so that sparse and dense scores can be added together during fusion.

## 2. In QueuePilot

| Where | What |
|---|---|
| `app/providers/embeddings.py` | `Embedder` protocol + `GeminiEmbedder` (calls `gemini-embedding-001` via google-genai SDK) |
| `app/config.py` | `embed_dim: int = 768` — pinned constant |
| `docs/final-build-plan/02-DATA-MODEL.md` | Pinecone index spec records model + 768 |
| `.env` / `.env.example` | `EMBED_DIM=768` |

**Ingest path:** `data/ingest.py` → `GeminiEmbedder.embed_documents(texts)` → 768-float dense
vector per ticket → upserted alongside a BM25 sparse vector into one Pinecone sparse-dense index.

**Query path:** `GeminiEmbedder.embed_query(text)` → 768-float query vector → fed to Pinecone
hybrid query together with a BM25 sparse query vector.

The `Embedder` *protocol* means retrieval code never imports `GeminiEmbedder` directly — only the
protocol type, so a future swap (e.g. Cohere, OpenAI) touches only `get_embedder()`.

## 3. Why this way

**Why Gemini `gemini-embedding-001`?**
Stack-locked in `docs/final-build-plan/01-TECH-STACK-LOCKED.md`.  Gemini is already the chat LLM
provider; reusing the same vendor reduces API surface and key management complexity.

**Why 768 dims?**
768 is the Matryoshka "sweet spot" for `gemini-embedding-001`: sufficient semantic richness for
customer-support ticket retrieval, small enough that Pinecone storage costs stay low.  Going higher
(e.g. 1536) would increase cost without meaningful retrieval quality improvement at ~3 k corpus size.

**Why dotproduct, not cosine?**
Pinecone requires `metric="dotproduct"` on sparse-dense indexes so that the sparse (BM25) and dense
(Gemini) scores can be fused additively.  For normalized vectors, dotproduct == cosine, so no
accuracy is lost.

**Why fix the dim now?**
Once the Pinecone index is created and tickets are ingested, changing the dimension requires
destroying and rebuilding the index plus re-embedding every ticket.  Pinning early (A3, before A5
Pinecone setup and A7 ingest) avoids that pain.

## 4. Verify it yourself

```bash
uv run python learn/02_embeddings.py
```

**Expected output (approximately):**
```
== A3: Gemini embeddings ==

Model : gemini-embedding-001
Dim   : 768

Text A: "My printer is offline and won't connect."
Text B: "The printer stopped working and I can't print anything."
Text C: "I need help booking a flight to Tokyo."

Vector length A: 768  ✓
Vector length B: 768  ✓
Vector length C: 768  ✓

Pairwise cosine similarities:
  A vs B (similar topic):    0.87  ← high: both describe a printer problem
  A vs C (different topic):  0.62  ← low: printer vs. travel
  B vs C (different topic):  0.60  ← low: printer vs. travel
```

The higher similarity between A and B (same topic) vs. A/C or B/C (different topic) proves the
embedding captures *meaning*, not just word overlap.

## 5. Self-quiz

1. Why can't you mix 768-dim and 1536-dim vectors in the same Pinecone index, even for the same
   model?
2. After we fix `EMBED_DIM=768` and ingest 3 000 tickets, a new Gemini model releases that produces
   better embeddings at 1024 dims.  What is the minimum set of steps required to adopt it?
3. Cosine similarity between two normalized vectors equals their dot product.  When would you
   *prefer* dot product even over cosine as a raw metric?

<details><summary>Answers</summary>

1. A vector index is compiled at creation time with a fixed-width column.  Inserting a vector of a
   different width is a type mismatch — the index cannot store or compare it.  Pinecone enforces
   this at the API level and returns a 400 error.

2. Minimum steps: (a) update `EMBED_DIM` in config + `.env`, (b) delete and recreate the Pinecone
   index with the new dimension, (c) re-embed all ~3 000 tickets with the new model, (d) re-fit
   BM25 if the tokeniser changed, (e) update `docs/final-build-plan/02-DATA-MODEL.md`.  There is no
   partial migration — the whole index must be rebuilt.

3. Dot product is preferable when vectors are *not* L2-normalized and magnitude carries information
   (e.g. importance scores, frequency-weighted embeddings).  For Pinecone hybrid fusion the reason
   is different: the index metric must be `dotproduct` so that sparse and dense partial scores can
   be summed; normalizing the vectors beforehand makes it equivalent to cosine.

</details>

## 6. Takeaway

Pinning the embedding dimension at ingest time is irreversible: every byte of the Pinecone index is
shaped around it, so choosing the right model + dim once (768, `gemini-embedding-001`) is cheaper
than a re-index later — and the Matryoshka property means we can always go smaller, never bigger,
without a rebuild.
