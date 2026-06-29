# Infra note (A5) — Pinecone sparse-dense store

> Infra note (not a numbered concept doc — NN 04/05 are reserved for A6 hybrid fusion and A8
> confidence). Task: `A5`. Code: `app/retrieval/pinecone_store.py`.

**Serverless sparse-dense index.** Pinecone "serverless" means you don't provision pods — you pay per
operation and the index scales itself. We create **one** index that stores *both* vectors per record:
the dense Gemini embedding (`values`) and the BM25 sparse vector (`sparse_values`). This single-index
layout is Pinecone's recommended hybrid approach: one `query()` call fuses both signals, instead of
querying two indexes and merging client-side.

**Why `metric="dotproduct"`.** Hybrid search requires the dot-product metric. Cosine/euclidean indexes
reject sparse vectors. Dot product is also what lets A6's alpha-weighting work: scaling the dense and
sparse values linearly scales their contribution to the combined score.

**Metadata rules.** Pinecone metadata accepts strings, numbers, booleans, and lists of strings — **not
null**. So `_clean_metadata` omits any `None` field (e.g. a ticket with no `priority`) rather than
storing `null`. We keep `queue`, `priority`, `type`, and a `snippet` for display/debugging.

**Namespaces** partition vectors inside one index. The real corpus lives in `tickets`; the live
integration test writes to a throwaway `test-a5` namespace and deletes it on teardown, so tests never
pollute the corpus and the index is reused by A7's ingest.

**Lifecycle: create → ready → upsert → query.** `ensure_index()` is idempotent: it checks
`has_index()`, creates the index with a built-in readiness `timeout` (no fragile manual polling), and
connects. It also guards against **dimension drift** — the pinned model dim
(`providers.embeddings.EMBED_DIM`) must equal `config.embed_dim`, else it raises (changing the index
dimension would require a full re-embed + re-index).

**Self-check:** Why must `None` metadata be omitted rather than stored? Why does hybrid need
dotproduct? What does `ensure_index()` assert before creating, and why?
