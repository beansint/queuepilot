# QueuePilot — Slice A: Foundation & Retrieval Loop (Design Spec)

**Date:** 2026-06-29
**Status:** Approved for implementation planning
**Author:** Vincent (with Claude Code)

---

## 0. Context

QueuePilot is a semi-public, portfolio-first **agentic AI ticketing system** for IT/helpdesk
workflows, built deliberately to close skill gaps for an *AI Developer (LLM & API Focus)* role and
to serve as a **learning vehicle** for LangGraph, hybrid retrieval, and LangSmith.

The full product is too large for one spec. It is decomposed into five slices (see
`2026-06-29-queuepilot-roadmap.md`). **This document specifies Slice A only.**

Slice A's job: prove the **retrieval + structured-output loop** before any orchestration wraps it.
This follows the project's own build-order rule — *do not build a complicated workflow before
proving the basic retrieval loop.*

### Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Job-fit posture | Lean core. No Azure / GraphQL / OpenAI-only wiring. Provider registry keeps OpenAI a drop-in. |
| Vector DB | Pinecone, **single sparse-dense index** (current recommended hybrid approach). |
| Dense embeddings | Gemini (fixed dimension, swappable interface). |
| Sparse vectors | BM25 via `pinecone-text`, generated locally. |
| Score fusion | `hybrid_score_norm(alpha)` — normalize sparse+dense at query time. |
| Chat LLM | Swappable provider registry (default cheap/fast: Groq/Gemini; OpenAI provable drop-in). **Not used in A's baseline.** |
| Corpus size | ~3,000 English-only tickets (configurable cap). |
| Baseline labeling | Pure retrieval **majority-vote** over neighbor labels — no LLM call in A. |
| Tooling | `uv`, Python 3.11+. |
| Learning layer | Core graded requirement — all four forms (see §7). |

---

## 1. Purpose & Success Criteria

A running FastAPI app where you `POST /analyze` with ticket text and receive a structured envelope:
**category, queue, priority, similar historical tickets (hybrid-retrieved, with scores), and a
naive blended confidence number** — *no LangGraph yet*.

**Success =**
1. Kaggle corpus ingested and normalized into one Pinecone sparse-dense index (~3k English tickets).
2. Hybrid retrieval returns genuinely relevant neighbors (validated on a fixture set).
3. `/analyze` returns the structured envelope (defined in §5) with derived labels + confidence v0.
4. Each concept has a learning doc + runnable script + self-quiz checkpoint (§7).
5. Build/typecheck + unit + integration tests green (§8).

**Explicit non-goals for A** (deferred to later slices, not skipped):
LangGraph workflow (B) · sentiment/SLA/escalation/clarification/suggested-reply (B) ·
dashboard + `--explain` debug mode (C) · LangSmith tracing & eval (C/D) · Docker/Render/auth (E).

---

## 2. Project Skeleton

```
queuepilot/
  app/
    main.py              # FastAPI app: /health + /analyze
    config.py            # pydantic-settings, env-driven config
    schemas.py           # Pydantic request/response models (the output envelope)
    providers/
      embeddings.py      # Gemini dense embedder behind an Embedder interface
      llm.py             # provider registry stub (Groq/Gemini/OpenAI) — defined, unused in A
    retrieval/
      sparse.py          # BM25 sparse vectors via pinecone-text
      pinecone_store.py  # index create / upsert / hybrid query
      hybrid.py          # alpha-weighted fusion (hybrid_score_norm) + result shaping
    analyze/
      baseline.py        # embed -> retrieve -> majority-vote labels -> confidence v0
  data/
    ingest.py            # load Kaggle CSV -> normalize -> upsert (one-time script)
    normalize.py         # text cleaning, field mapping, language filter
  learn/                 # runnable concept scripts (notebooks-as-scripts)
    01_embeddings.py
    02_bm25_sparse.py
    03_hybrid_fusion.py
  docs/learn/
    01-embeddings.md
    02-hybrid-retrieval.md
    03-confidence-v0.md
  tests/
    test_normalize.py
    test_hybrid.py
    test_baseline.py
    test_analyze_endpoint.py
  pyproject.toml         # uv-managed, Python 3.11+
  .env.example
  README.md
```

**Design-for-isolation notes:**
- `providers/embeddings.py` exposes an `Embedder` protocol (`embed(texts) -> list[vector]`) so the
  embedding model/dimension is swappable without touching retrieval.
- `retrieval/*` knows nothing about FastAPI; it is a pure library callable from scripts and tests.
- `analyze/baseline.py` is the only place that composes embed + retrieve + derive, so Slice B can
  replace it with a LangGraph runtime behind the same `/analyze` contract.

---

## 3. Data Flow — Ingest (one-time)

```
Kaggle CSV
  -> normalize.py
       - filter to English
       - map fields: subject + body -> text; keep queue, priority, type labels; agent answer -> reply corpus
       - clean (strip signatures/quoted threads where cheap)
       - cap to N (default 3000), log how many were dropped and why
  -> for each ticket:
       - Gemini dense embed (fixed dim)
       - BM25 sparse vector (pinecone-text)
  -> upsert to ONE Pinecone sparse-dense index
       metadata: { queue, priority, type, text_snippet }
```

Cost/honesty guardrails: capped subset only; ingest logs `indexed=N, dropped=M (reasons)` so
coverage is never silently overstated.

## 4. Data Flow — `/analyze` (per request)

```
ticket text
  -> dense query vector (Gemini)  +  sparse query vector (BM25)
  -> hybrid_score_norm(dense, sparse, alpha)        # normalize so sparse doesn't dominate
  -> Pinecone hybrid query (top_k)                  # single call, single index
  -> neighbors [{score, queue, priority, type, snippet}]
  -> baseline.py:
       - category/queue/priority = majority vote over neighbor labels
       - confidence v0 = blend(top_score, neighbor_label_agreement)
  -> structured envelope (see §5)
```

No LLM call in this path for Slice A. `alpha` is configurable (default ~0.5) and documented in the
hybrid learning doc.

---

## 5. The Output Envelope (forward-compatible)

A single Pydantic model designed **now** to hold everything later slices add, so the API shape is
stable from A onward. Fields owned by later slices are present as `Optional` and omitted/`null` in A.

```python
class SimilarTicket(BaseModel):
    score: float
    queue: str | None
    priority: str | None
    type: str | None
    snippet: str

class AnalyzeResponse(BaseModel):
    # --- Slice A populates these ---
    category: str | None            # derived via majority vote
    queue: str | None
    priority: str | None
    confidence: float               # blended v0 (retrieval-only)
    similar_tickets: list[SimilarTicket]

    # --- reserved for later slices (None in A) ---
    sentiment: dict | None = None        # B: {frustration, negativity}
    sla_risk: float | None = None        # B
    escalate: bool | None = None         # B
    clarification: list[str] | None = None  # B
    suggested_reply: str | None = None   # B
    trace: dict | None = None            # C: LangSmith run summary
```

`AnalyzeRequest`: `{ text: str (max length enforced), metadata?: dict }`.

---

## 6. Confidence v0

Deliberately **not** raw LLM self-confidence (project principle: explainable + tunable).
Slice A's blend uses only what retrieval gives us:

```
confidence_v0 = w1 * normalized_top_score
              + w2 * neighbor_label_agreement   # fraction of top-k sharing the winning queue label
```

Weights live in config. Later slices add classification certainty, route/priority consistency,
missing-info penalties, and escalation-risk penalties to this same function.

---

## 7. Learning Artifacts (CORE GRADED REQUIREMENT)

Built *with* the code, not after. All four forms:

1. **Annotated concept docs** (`docs/learn/`):
   - `01-embeddings.md` — what an embedding is, Gemini dimensions, cosine vs dotproduct, why a fixed
     dimension locks the index.
   - `02-hybrid-retrieval.md` — dense vs sparse, BM25 intuition, why scores must be normalized,
     what `alpha` tunes, single sparse-dense index rationale.
   - `03-confidence-v0.md` — why blended numeric confidence beats raw LLM confidence.
2. **Runnable concept scripts** (`learn/`): each runs in isolation against a tiny inline corpus —
   `01_embeddings.py`, `02_bm25_sparse.py`, `03_hybrid_fusion.py`.
3. **Guided checkpoints + self-quiz**: each `docs/learn/*.md` ends with 2–3 "can you explain…?"
   questions and a working/not-working gate before moving on.
4. **Opt-out in-app `--explain` debug mode**: **deferred to Slice C** (needs the dashboard/trace).
   Noted here as deferred, not skipped.

---

## 8. Testing & Verification

- **Unit (no network):** `normalize` field mapping + language filter; `hybrid_score_norm`;
  majority-vote derivation; `confidence_v0`.
- **Integration:** upsert ~20-ticket fixture corpus to a throwaway Pinecone namespace; assert a
  known query returns the expected neighbor in top-k.
- **Endpoint:** `/analyze` with a mocked store — asserts envelope shape, status codes, max-length
  rejection.
- **Build/typecheck:** `uv` install clean; `ruff` + `mypy` (or `pyright`) pass.
- **Honest reporting:** the verification summary states which rubric items ran vs. N/A (no UI/a11y
  in A → marked N/A with reason).

---

## 9. Tooling, Cost & Security Guardrails

- `uv` for env/deps; Python 3.11+ (system is 3.9 — a fresh venv is required).
- Gemini embeddings run on the capped ~3k subset only; Pinecone free tier, one index.
- All provider keys server-side via `pydantic-settings`; `.env.example` documents every key
  (`GEMINI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX`, provider keys, `MAX_INPUT_CHARS`,
  `CORPUS_CAP`, `HYBRID_ALPHA`).
- No secrets committed; `.env` gitignored.

---

## 10. Risks & Open Questions

- **Gemini embedding dimension** must be fixed before index creation; changing it later forces a
  reindex. Pin it in config and document in `01-embeddings.md`.
- **Kaggle dataset schema** (column names, language field) must be confirmed against the actual CSV
  during ingest implementation; `normalize.py` isolates this so a schema change is one file.
- **BM25 corpus fit:** `pinecone-text` BM25 needs to be fit on the corpus vocabulary; ingest must
  persist the fitted model params for query-time encoding.
```
