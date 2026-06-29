# 06 — Architecture

## Module layout
```
queuepilot/
  app/
    main.py              # FastAPI: /health + /analyze
    config.py            # pydantic-settings (env-driven)
    schemas.py           # API contract models (see 03)
    providers/
      embeddings.py      # Embedder protocol + Gemini impl
      llm.py             # provider registry (Groq/Gemini/OpenAI) — used from Slice B
    retrieval/
      sparse.py          # BM25 (pinecone-text), fit + persist
      pinecone_store.py  # index create/upsert/hybrid query
      hybrid.py          # hybrid_score_norm(alpha) + result shaping
    analyze/
      baseline.py        # Slice A composition (swapped for LangGraph in B)
  data/
    ingest.py            # CSV -> normalize -> embed -> upsert (one-time)
    normalize.py         # field mapping + language filter (isolates Kaggle schema)
    artifacts/           # bm25_params.json, etc.
  learn/                 # runnable concept scripts (01_, 02_, 03_)
  docs/learn/            # annotated concept docs + self-quiz
  tests/
```

## Boundaries (design for isolation)
- **`providers/embeddings.py`** exposes an `Embedder` protocol → the embedding model/dimension is
  swappable without touching retrieval.
- **`retrieval/*`** is a pure library; it imports no FastAPI and is callable from scripts/tests.
- **`analyze/baseline.py`** is the only place composing embed+retrieve+derive → Slice B replaces it
  with a LangGraph runtime **behind the same `/analyze` contract** (see `03`). The endpoint in
  `main.py` does not change shape.
- **`data/normalize.py`** isolates the Kaggle CSV schema → a dataset change touches one file.

## Data flow — ingest (one-time)
```
Kaggle CSV
  -> normalize (English filter, field map, clean, cap ~3k)
  -> per ticket: Gemini dense embed + BM25 sparse
  -> upsert to one Pinecone sparse-dense index (metadata: queue, priority, type, snippet)
  -> log indexed=N, dropped=M (reasons)
  (persist BM25 fit params to data/artifacts/)
```

## Data flow — `/analyze` (per request, Slice A)
```
text
  -> dense query vec (Gemini) + sparse query vec (BM25, loaded fit params)
  -> hybrid_score_norm(dense, sparse, alpha)        # normalize so sparse can't dominate
  -> Pinecone hybrid query (top_k)                  # single call, single index
  -> neighbors [{score, queue, priority, type, snippet}]
  -> baseline: majority-vote labels + confidence v0
  -> AnalyzeResponse envelope
```

## How Slice B plugs in
`analyze/baseline.py` → `analyze/graph.py` (LangGraph). Nodes: classify → retrieve → assess-missing
→ score → decide(answer/clarify/escalate) → draft reply. The graph fills the reserved envelope
fields (`sentiment`, `sla_risk`, `escalate`, `clarification`, `suggested_reply`). `main.py` keeps
calling one `analyze(text)` entrypoint; only its internals change.

## Cross-cutting
- Config + secrets: `pydantic-settings`, server-side only (`01`).
- Observability (Slice C): LangSmith tracing wraps the graph; `trace` summary added to the envelope.
- Opt-out `--explain` debug mode (Slice C): surfaces node-by-node reasoning, retrieval scores, and
  the confidence breakdown; never forced into the normal dashboard path.
