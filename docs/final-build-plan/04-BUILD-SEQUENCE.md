# 04 — Build Sequence

Slices map to milestones M-A…M-E in both trackers. Issues are mirrored 1:1
(GitHub `#N` ↔ Linear `BEA-…`).

## Slice order
A (foundation+retrieval) → B (LangGraph workflow) → C (dashboard+tracing) → D (eval) → E (deploy).
Build A fully before B — prove the retrieval/output loop before wrapping a graph around it.

---

## Slice A — Foundation & Retrieval Loop (M-A)
Branch `slice-a-foundation`. Tasks are ordered; deps noted. 📚 = ships a learning artifact.

| ID | Task | GH | Linear | Deps |
|---|---|---|---|---|
| <a id="a1"></a>A1 | Project skeleton & tooling (uv, FastAPI `/health`, config, `.env.example`) | #1 | BEA-128 | — |
| <a id="a2"></a>A2 | Output envelope schemas (`AnalyzeRequest`/`AnalyzeResponse`/`SimilarTicket`) | #2 | BEA-129 | A1 |
| <a id="a3"></a>A3 📚 | Gemini embeddings provider (`Embedder` protocol, pin `EMBED_DIM`) | #3 | BEA-130 | A1 |
| <a id="a4"></a>A4 📚 | BM25 sparse vectors (`pinecone-text`, persist fit params) | #4 | BEA-131 | A1 |
| <a id="a5"></a>A5 | Pinecone sparse-dense store (create/upsert/hybrid query) | #5 | BEA-132 | A3,A4 |
| <a id="a6"></a>A6 📚 | Hybrid fusion + alpha (`hybrid_score_norm`) | #6 | BEA-133 | A5 |
| <a id="a7"></a>A7 | Kaggle ingest + normalize (English filter, cap ~3k, log dropped) | #7 | BEA-134 | A3,A4 |
| <a id="a8"></a>A8 📚 | Baseline `/analyze` (majority-vote labels + confidence v0) | #8 | BEA-135 | A2,A6 |
| <a id="a9"></a>A9 | Tests & verification (unit + integration + endpoint) | #9 | BEA-136 | A8 |
| <a id="a10"></a>A10 📚 | Learning checkpoints + README | #10 | BEA-137 | A9 |

**Per-task acceptance** ("Done when") lives on each issue. Definition of done is binding.

### Slice A exit criteria (then flip repo public)
- `/analyze` returns genuinely relevant neighbors via real hybrid retrieval on ~3k tickets.
- Every 📚 task has doc + runnable script + self-quiz, logged in `LEARNING-LOG.md`.
- Tests green; README complete; `main` clean via squash-merged PR.

---

## Slices B, D, E (epics; expand into tasks when started)

| Slice | Milestone | GH | Linear | Outcome |
|---|---|---|---|---|
| B — Agentic Workflow | M-B | #11 | BEA-138 | LangGraph state machine behind `/analyze`; full envelope. |
| D — Evaluation | M-D | #13 | BEA-140 | LangSmith offline + online eval, experiments, feedback. |
| E — Deploy & Harden | M-E | #14 | BEA-141 | Docker → Render, invite-code auth, rate limiting. |

When starting a slice, expand its epic into task issues in **both** trackers and add a task table here.

---

## Slice C — Dashboard + Observability (M-C)
Branch `slice-c-dashboard`. Epic `#12` / `BEA-139`. Tasks ordered; deps noted. 📚 = ships a learning
artifact. Design detail: `09-SLICE-C-DESIGN.md`.

| ID | Task | GH | Linear | Deps |
|---|---|---|---|---|
| <a id="c1"></a>C1 | LangSmith wiring: env-driven client, `@traceable` on chat-model registry calls, graceful no-op without a key | #12 | BEA-139 | — |
| <a id="c2"></a>C2 | `trace` payload assembly (`enabled, run_id, url, latency_ms, project`) wired into `/analyze` response | #12 | BEA-139 | C1 |
| <a id="c3"></a>C3 | `TicketState` accumulator: each graph node appends a `{node, summary, data}` step | #12 | BEA-139 | — |
| <a id="c4"></a>C4 | `?explain` query param on `POST /analyze`; `debug` field populated from the accumulator, `null` otherwise | #12 | BEA-139 | C3 |
| <a id="c5"></a>C5 ⏸️ | *(paused — UI-design hold)* Vite/React/TypeScript/Tailwind/shadcn console scaffold, built to static assets | TBD | TBD | — |
| <a id="c6"></a>C6 | FastAPI static-asset mount for the built console — **backend wiring ships now**; UI half that renders results ⏸️ *(paused — UI-design hold)* | TBD | TBD | C5 |
| <a id="c7"></a>C7 📚 | Tracing concept doc + runnable script + self-quiz (`docs/learn/06-tracing.md` / `learn/06_tracing.py`) | TBD | TBD | C2 |
| <a id="c8"></a>C8 📚 | Explainability concept doc + runnable script + self-quiz (`docs/learn/07-explainability.md` / `learn/07_explainability.py`) | TBD | TBD | C4 |
| <a id="c9"></a>C9 | Tests: `trace` no-op path, `debug` populated/absent paths, mocked-chat offline coverage + gated live LangSmith integration test | TBD | TBD | C2,C4 |

### Slice C exit criteria
- Every `/analyze` call carries a `trace` summary (`enabled: false` gracefully when no LangSmith key
  is configured); LangSmith UI shows nested runs for chat-model calls when a key is present.
- `POST /analyze?explain=true` returns a populated `debug.steps` reasoning trail; default calls keep
  `debug: null`. No change to existing response shape for callers that don't pass `explain`.
- Every 📚 task has doc + runnable script + self-quiz, logged in `LEARNING-LOG.md`.
- Tests green (including the offline `--explain` + tracing-no-op paths); `main` clean via
  squash-merged PR.
- Console (C5, UI half of C6) explicitly **not** required for exit — tracked separately, resumes
  after the UI-design session.
