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
| `app/providers/embeddings.py` | `Embedder` protocol + `VoyageEmbedder` (default) + `GeminiEmbedder` (drop-in) + provider registry |
| `app/config.py` | `embed_dim: int = 1024`, `embedding_provider: str = "voyage"` |
| `docs/final-build-plan/02-DATA-MODEL.md` | Pinecone index spec — Voyage, 1024 dims, registry-swappable |
| `.env` / `.env.example` | `EMBEDDING_PROVIDER=voyage`, `EMBED_DIM=1024` |

**Ingest path:** `data/ingest.py` → `get_embedder().embed_documents(texts)` → 1024-float dense
vector per ticket → upserted alongside a BM25 sparse vector into one Pinecone sparse-dense index.

**Query path:** `get_embedder().embed_query(text)` → 1024-float query vector → fed to Pinecone
hybrid query together with a BM25 sparse query vector.

### Provider registry

The `Embedder` *protocol* defines the interface; a registry dict maps provider names to classes:

```python
_PROVIDERS = {"voyage": VoyageEmbedder, "gemini": GeminiEmbedder}
```

`get_embedder()` reads `settings.embedding_provider`, looks up the class, constructs it with the
matching API key, and returns it.  `EMBED_DIM` is resolved at import time from the active
provider's class attribute:

```python
EMBED_DIM: int = _PROVIDERS[get_settings().embedding_provider].DIM  # 1024 for voyage
```

This single integer is the source of truth imported by `pinecone_store.ensure_index`, so changing
`EMBEDDING_PROVIDER` in `.env` automatically propagates the correct index width.  To add a third
provider (e.g. OpenAI `text-embedding-3-small`, 1536 dims): (1) implement the class with
`DIM = 1536` and `embed_documents` / `embed_query`, (2) add it to `_PROVIDERS` and
`_PROVIDER_KEY_ATTRS`, (3) update `app/config.py` with the new key, (4) recreate the Pinecone
index if the dim changes.  Zero changes to retrieval or ingest code.

## 3. Why this way

**Why Voyage `voyage-3.5-lite` as the default? (D11)**
Voyage gives 200 M free tokens per month.  Our corpus is ~0.35 M tokens, so ingest costs $0 with
no rate-limit throttle.  Gemini `gemini-embedding-001` is still a registry drop-in — switching
requires only `EMBEDDING_PROVIDER=gemini` in `.env` plus a full re-index.

**Why 1024 dims?**
`voyage-3.5-lite` outputs fixed 1024-dimensional vectors (not Matryoshka), giving good semantic
richness for customer-support retrieval at a modest storage cost.  Pinecone's free tier handles
~3 k × 1024-float records comfortably.

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
== A3: Voyage embeddings (voyage-3.5-lite) ==

Model : voyage-3.5-lite
Dim   : 1024

Text A: "My printer is offline and won't connect."
Text B: "The printer stopped working and I can't print anything."
Text C: "I need help booking a flight to Tokyo."

Vector length A: 1024  ✓
Vector length B: 1024  ✓
Vector length C: 1024  ✓

Pairwise cosine similarities:
  A vs B (similar topic):    ~0.90  ← high: both describe a printer problem
  A vs C (different topic):  ~0.60  ← low: printer vs. travel
  B vs C (different topic):  ~0.58  ← low: printer vs. travel
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
shaped around it, so choosing the right model + dim once (1024, `voyage-3.5-lite`) is cheaper
than a re-index later.  The provider registry means you can prove provider-agnosticism in an
interview without rebuilding the index — just point to the `_PROVIDERS` dict and `EMBED_DIM` chain.
