# Build Plan — Slice A: Foundation & Retrieval Loop

Milestone **M-A**. Each task below maps to one GitHub issue and one Linear issue.
Design reference: `docs/superpowers/specs/2026-06-29-queuepilot-slice-a-design.md`.

Tasks are ordered. Earlier tasks unblock later ones; dependencies noted as `(after Ax)`.

---

### A1 — Project skeleton & tooling
Set up `uv` project (Python 3.11+), `pyproject.toml`, `ruff` + `mypy`/`pyright`, FastAPI app with
`/health`, `app/config.py` (`pydantic-settings`), `.env.example` documenting every key.
**Done when:** `uv run` boots the app, `/health` returns 200, lint + typecheck pass clean.

### A2 — Output envelope schemas  *(after A1)*
`app/schemas.py`: `AnalyzeRequest` (text + max-length guard) and the forward-compatible
`AnalyzeResponse` envelope + `SimilarTicket` (Slice-A fields populated, later-slice fields `Optional`).
**Done when:** models validate; max-length rejection unit-tested.

### A3 — Gemini embeddings provider  *(after A1)* · 📚 learning
`app/providers/embeddings.py`: `Embedder` protocol + Gemini dense impl, fixed dimension pinned in
config. Ship `learn/01_embeddings.py` + `docs/learn/01-embeddings.md`.
**Done when:** embedding a string returns a fixed-length vector; learn script runs standalone.

### A4 — BM25 sparse vectors  *(after A1)* · 📚 learning
`app/retrieval/sparse.py`: BM25 via `pinecone-text`, fit on corpus vocab, **persist fitted params**
for query-time encoding. Ship `learn/02_bm25_sparse.py`.
**Done when:** a query string yields a `{indices, values}` sparse vector; fit params persist/reload.

### A5 — Pinecone sparse-dense store  *(after A3, A4)*
`app/retrieval/pinecone_store.py`: create the single sparse-dense (dotproduct) index, upsert
records with metadata `{queue, priority, type, snippet}`, hybrid query.
**Done when:** integration test upserts ~20-ticket fixture to a throwaway namespace and queries it.

### A6 — Hybrid fusion + alpha  *(after A5)* · 📚 learning
`app/retrieval/hybrid.py`: `hybrid_score_norm(dense, sparse, alpha)` normalization + result shaping.
Ship `learn/03_hybrid_fusion.py` + `docs/learn/02-hybrid-retrieval.md` (dense vs sparse, why
normalize, what alpha tunes).
**Done when:** fusion unit-tested; alpha is config-driven; doc explains the gotcha.

### A7 — Kaggle ingest + normalize
`data/normalize.py` (English filter, field mapping subject+body→text, keep queue/priority/type,
agent-answer→reply corpus, cleaning) and `data/ingest.py` (load CSV → normalize → cap ~3k → embed
dense+sparse → upsert). Logs `indexed=N, dropped=M (reasons)`.
**Done when:** running ingest populates the index with ~3k records; normalize is unit-tested; the
actual Kaggle column schema is confirmed and isolated in `normalize.py`.

### A8 — Baseline `/analyze`  *(after A2, A6)* · 📚 learning
`app/analyze/baseline.py`: embed → hybrid retrieve → majority-vote category/queue/priority →
confidence v0 = blend(top_score, neighbor_label_agreement). Wire `POST /analyze` in `app/main.py`.
Ship `docs/learn/03-confidence-v0.md` (why blended > raw LLM confidence).
**Done when:** `/analyze` returns the full envelope against the live index.

### A9 — Tests & verification  *(after A8)*
Unit: `normalize`, `hybrid_score_norm`, majority-vote, confidence v0. Integration: fixture-corpus
retrieval. Endpoint: `/analyze` with mocked store (shape, status, max-length). Build/typecheck green.
**Done when:** full suite passes; verification summary states ran-vs-N/A honestly.

### A10 — Learning checkpoints & README  *(after A9)* · 📚 learning
Add end-of-phase checkpoint + self-quiz blocks to each `docs/learn/*.md`; write top-level `README.md`
(what QueuePilot is, how to run ingest + the app, how to run each `learn/` script).
**Done when:** every concept has doc + runnable script + self-quiz; README lets a stranger run it.

---

## Slice A exit criteria (flip repo public after this)
- `/analyze` returns genuinely relevant neighbors via real hybrid retrieval on ~3k tickets.
- All learning artifacts present (docs + scripts + self-quizzes).
- Tests green; README complete; `main` clean via squash-merged PR.
