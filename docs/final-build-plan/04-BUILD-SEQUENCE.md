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

## Slices B–E (epics; expand into tasks when started)

| Slice | Milestone | GH | Linear | Outcome |
|---|---|---|---|---|
| B — Agentic Workflow | M-B | #11 | BEA-138 | LangGraph state machine behind `/analyze`; full envelope. |
| C — Dashboard + Observability | M-C | #12 | BEA-139 | Console + opt-out `--explain` + LangSmith tracing. |
| D — Evaluation | M-D | #13 | BEA-140 | LangSmith offline + online eval, experiments, feedback. |
| E — Deploy & Harden | M-E | #14 | BEA-141 | Docker → Render, invite-code auth, rate limiting. |

When starting a slice, expand its epic into task issues in **both** trackers and add a task table here.
