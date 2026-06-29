# 03 — BM25 / Sparse Vectors

> **Learning artifact** — every task that introduces a concept ships one of these.
> Pattern: `docs/learn/_TEMPLATE.md` · Log it in `docs/final-build-plan/LEARNING-LOG.md`
> Task: `A4` · Runnable companion: `uv run python learn/03_bm25_sparse.py`

Keep it short and concrete. Six fixed sections, always in this order.

## 1. Concept

**BM25** (Best Match 25) is a classical *lexical* (sparse) ranking function from information
retrieval. Unlike dense embeddings, which map text to a continuous vector of floating-point numbers,
BM25 produces a **sparse vector**: a set of `(token_id, weight)` pairs — one per vocabulary term
that actually appears in the text. All other dimensions are implicitly zero.

The weight of each term is driven by two intuitions:

1. **Term Frequency (TF):** A token that appears many times in a document is probably important —
   but with *diminishing returns* (doubling the count doesn't double the relevance). BM25 applies a
   saturation curve controlled by the parameter `k1` (default 1.2).

2. **Inverse Document Frequency (IDF):** A token that appears in *every* document (e.g. "the") is
   uninformative. A term that appears in only 2 of 3 000 documents is a strong discriminator. IDF is
   the log of the ratio N/df (total docs ÷ docs containing the term).

3. **Length normalisation:** Longer documents naturally contain more tokens, inflating TF counts.
   BM25 scales TF relative to the document's length vs. the corpus average length, controlled by
   parameter `b` (default 0.75).

Put together, the BM25 score of document d for query q is:

```
score(q, d) = sum over query terms t of:
    IDF(t) * (TF(t,d) * (k1 + 1)) / (TF(t,d) + k1 * (1 - b + b * |d| / avgdl))
```

where `|d|` is document length and `avgdl` is the average document length in the corpus.

Pinecone's hybrid index stores this as a sparse vector with two parallel arrays:
```json
{ "indices": [613153351, 4220927227], "values": [0.62, 0.41] }
```
`indices` are hashed token IDs; `values` are the BM25 weights.

## 2. In QueuePilot

File: `app/retrieval/sparse.py`

- `SparseVector` TypedDict mirrors the `sparse_vector` shape Pinecone expects.
- `BM25SparseEncoder` wraps `pinecone_text.sparse.BM25Encoder`:
  - `fit(corpus)` — called once during ingest on all ticket texts.
  - `encode_documents(texts)` — called during ingest to produce sparse vectors for upsert.
  - `encode_query(text)` — called at query time (per `/analyze` request).
  - `save(path)` / `load(path)` — persist fitted vocabulary params to
    `data/artifacts/bm25_params.json` so query-time encoding uses the same vocabulary as ingest.

BM25 is the **sparse half** of our Pinecone sparse-dense index. The **dense half** is the 768-dim
Gemini embedding from A3. Both are upserted together and queried together via `alpha`-weighted hybrid
search (A6).

## 3. Why this way

**Why sparse retrieval at all?** Dense embeddings excel at semantic similarity — they understand that
"cannot access my account" and "login fails" mean the same thing. But they struggle with
*lexical precision*: a query like "error code 809" or "VPN port 1723" may have low cosine similarity
to a relevant ticket that uses those exact tokens, because the model spreads meaning across all
dimensions rather than pinning weight on the specific string. BM25 catches those exact-match signals
that dense embeddings routinely miss.

**Why BM25 specifically?** It is the standard TF-IDF variant used by Elasticsearch, Solr, and most
production search engines. `pinecone-text` provides a drop-in encoder that produces the exact
`{indices, values}` shape Pinecone needs. No API key, no network calls, runs fully offline.

**Why persist the fit artifact?** BM25 IDF weights depend on the corpus vocabulary. If we refit on
each query, IDF values would change with every request and be inconsistent with what was indexed.
Fitting at ingest time and loading the same params at query time guarantees consistency.

**Alternatives rejected:** TF-IDF (BM25 generalises it with better saturation); SPLADE (learned
sparse model, requires GPU training); pure dense-only retrieval (misses exact-match keyword queries).

## 4. Verify it yourself

```bash
uv run python learn/03_bm25_sparse.py
```

**Expected output:**

- A small support-ticket corpus is fit (with a progress bar from `pinecone-text`).
- A keyword-heavy query ("VPN error code 809") is encoded and the sparse vector is printed.
- The script demonstrates that rare/specific terms (e.g. "vpn", "809") receive **higher weights**
  than common terms, proving the IDF intuition.
- A round-trip save/load is shown and the loaded encoder produces identical output.

## 5. Self-quiz

1. A document contains the word "error" 20 times in 500 words. Another contains it 2 times in 50
   words. BM25's length normalisation makes their TF contribution more similar. Why is this
   desirable?
2. You have a query "VPN error 809". The token "error" appears in 2 800 of 3 000 corpus documents;
   "809" appears in only 4. Which token will dominate the BM25 score, and why?
3. Why must the BM25 encoder be fit at *ingest time* and **not** refit on each query?

<details><summary>Answers</summary>

1. A 20-occurrence word in a 500-word document is not necessarily more relevant than a 2-occurrence
   word in a 50-word document — both have the same underlying density (4%). Length normalisation
   removes the bias toward verbose documents, making TF a fairer signal of true topical focus.

2. "809" dominates because its IDF is very high (log(3000/4) ≈ 6.6) while "error"'s IDF is near
   zero (log(3000/2800) ≈ 0.07). Rare, specific terms signal strong topical match; common terms add
   almost nothing.

3. IDF values are computed from `df` (document frequency per term) which is a property of the
   **indexed corpus**. If you refit at query time you'd have different (or single-document) counts
   that would not match the weights used during indexing, making the dot-product scores meaningless.

</details>

## 6. Takeaway

BM25 gives us the lexical half of hybrid retrieval — it assigns high weight to rare, specific tokens
that dense embeddings dilute, so exact-match queries like error codes or product names always find
their best hit.
