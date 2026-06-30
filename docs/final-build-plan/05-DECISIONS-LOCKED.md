# 05 — Decisions Locked 🔒

ADR-style log of decisions already made. **Do not relitigate without explicit user sign-off.**
If a decision changes, append a new entry (don't edit history) and update the affected locked doc.

All decisions below: **2026-06-29**, during the initial brainstorm.

---

### D1 — Lean job-fit posture
**Choice:** build the clean FastAPI+LangGraph+Pinecone+LangSmith core; **defer** Azure Service Bus,
GraphQL, and OpenAI-only wiring.
**Considered:** max box-coverage (wire Azure + GraphQL + OpenAI); core+Azure-only.
**Why:** cheapest/cleanest; Azure/GraphQL are framed as transferable in interviews. Azure Service
Bus is the one "essential" left unchecked — accepted trade-off.

### D2 — Pinecone single sparse-dense index for hybrid
**Choice:** one index holding dense+sparse; supply our own vectors.
**Considered:** Pinecone integrated sparse model; dense-only now.
**Why:** current Pinecone-recommended approach (verified against live docs); genuine hybrid checks
the "hybrid retrieval" gap. Requires query-time score normalization.

### D3 — Dense = Gemini, Sparse = BM25 (`pinecone-text`) *(superseded by D11 for the default provider)*
**Choice:** Gemini dense embeddings + locally-generated BM25 sparse.
**Why:** low cost; Gemini gives only dense, so BM25 supplies the sparse half. Dimension is fixed at
first index creation (see `02`).
*Note: D11 switches the default dense provider to Voyage `voyage-3.5-lite` (1024 dims). Gemini
remains a registry drop-in via `EMBEDDING_PROVIDER=gemini`.*

### D4 — Swappable LLM provider registry (OpenAI a drop-in)
**Choice:** small provider abstraction defaulting to a cheap/fast model; OpenAI selectable.
**Considered:** OpenAI-only; Gemini-only.
**Why:** near-zero cost, demonstrates provider abstraction, AND lets us show OpenAI working (named
in the job). Not used in Slice A's baseline.

### D5 — Learning layer is a core graded requirement
**Choice:** every slice ships all four forms — annotated concept docs, runnable concept scripts,
checkpoints/self-quiz, and an opt-out in-app `--explain` debug mode (lands in Slice C).
**Why:** the project is also a learning vehicle for real skill gaps; skipping teaching artifacts
defeats a primary goal.

### D6 — Spec Slice A fully; roadmap B–E
**Choice:** full buildable spec for Slice A now; B–E as lightweight epics expanded when started.
**Why:** prove the retrieval loop before over-designing later phases whose shape depends on A.

### D7 — Slice A baseline uses pure retrieval majority-vote (no LLM)
**Choice:** derive category/queue/priority from neighbor labels; confidence v0 = blend(top score,
label agreement).
**Why:** isolates "does retrieval work?" before the LLM enters in Slice B; cheapest and explainable.

### D8 — Corpus: ~3k English-only tickets (configurable cap)
**Choice:** `CORPUS_CAP` default 3000, English filter.
**Why:** cheap embed cost, inside Pinecone free tier, enough for useful retrieval; raise later.

### D9 — Two-repo strategy
**Choice:** `queuepilot` flagship (private until end of Slice A, then public; clean `main`,
branch+PR per slice) + `queuepilot-lab` (private permanent sandbox for experiments).
**Why:** recruiters should land on a working demo, not a half-scaffold; experiments stay out of the
flagship's history.

### D10 — Deploy target: Docker → Render
**Choice:** Dockerized FastAPI on Render, same app serves UI + API.
**Why:** simplest demo-link path; deployment is part of the portfolio story.

### D11 — Embeddings provider: Voyage `voyage-3.5-lite` (1024 dims) behind a swappable registry (**supersedes D3**)
**Date:** 2026-06-30.
**Choice:** Default embedding provider is Voyage `voyage-3.5-lite` at 1024 dims, selected via
`EMBEDDING_PROVIDER=voyage`. Provider is resolved at runtime through a registry
(`_PROVIDERS` dict in `app/providers/embeddings.py`); Gemini `gemini-embedding-001` (768 dims)
remains a verified drop-in (`EMBEDDING_PROVIDER=gemini`).
**Why:** Voyage gives **200 M free tokens** per month — our ~0.35 M-token corpus ingests at $0
with no rate-limit grind. The registry design keeps OpenAI / Gemini as provable drop-ins, which
covers the job description's OpenAI mention without wiring it as the default. `EMBED_DIM` resolves
to the active provider's dimension at import time so `pinecone_store.ensure_index` always asserts
the right index width.
