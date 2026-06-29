# 02 — Data Model (LOCKED 🔒)

## Source dataset
Kaggle multilingual customer-support ticket dataset. v1 filters to **English** and caps the corpus
(`CORPUS_CAP`, default ~3000). The exact CSV column names are confirmed during A7 and isolated in
`data/normalize.py` so a schema change touches one file.

## Normalized ticket record (post-`normalize.py`)
```python
class TicketRecord(BaseModel):
    id: str                 # stable id (source row id or hash)
    text: str               # subject + body, cleaned
    queue: str | None       # label
    priority: str | None    # label
    type: str | None        # label (a.k.a. category source)
    answer: str | None      # agent answer -> reply corpus (kept for later slices)
    language: str           # filtered to "en" in v1
```

## Pinecone index spec
- **One index**, sparse-dense, metric **dotproduct** (required for hybrid).
- **Dense vector:** Gemini embedding, dimension `EMBED_DIM` — **PINNED AT A3** (record the exact
  value here once chosen; do not change without a reindex).
- **Sparse vector:** BM25 `{indices, values}` from `pinecone-text`.
- **Metadata stored per record:**
  ```json
  { "queue": "...", "priority": "...", "type": "...", "snippet": "first ~N chars of text" }
  ```
- **ID:** the `TicketRecord.id`.
- **Namespace:** `tickets` for the corpus; throwaway namespaces (e.g. `test-*`) for integration tests.

## BM25 fit artifact
BM25 must be **fit on the corpus vocabulary at ingest** and its params **persisted** (e.g.
`data/artifacts/bm25_params.json`) so query-time encoding uses the same vocabulary. Query path loads
this artifact; it is NOT refit per request.

## Retrieval output shape (internal)
```python
class Neighbor(BaseModel):
    score: float            # fused, normalized
    queue: str | None
    priority: str | None
    type: str | None
    snippet: str
```
This maps directly to `SimilarTicket` in the API contract (`03`).

## Cost / honesty guardrails
Ingest logs `indexed=N, dropped=M (reasons)`. Never silently truncate coverage.
