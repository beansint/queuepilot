# Learning Log

The learning layer is a **core graded requirement** (`05-DECISIONS-LOCKED.md` D5). Update this log as
you complete each task. A task is not done until its row is `done` with all artifacts present.

## The repeatable pattern (do this for EVERY task that touches a concept)
This is the baked-in foundation — not optional, not only for "AI" tasks. Each such task produces:

1. **Concept doc** — `docs/learn/NN-<slug>.md`, copied from **`docs/learn/_TEMPLATE.md`**
   (6 fixed sections: Concept · In QueuePilot · Why this way · Verify it yourself · Self-quiz · Takeaway).
2. **Runnable script** — `learn/NN_<slug>.py`, copied from **`learn/_template.py`**; runs standalone
   via `uv run python learn/NN_<slug>.py` and prints output that *proves* the concept.
3. **A row in this log** — set to `done` only when doc + script + self-quiz all exist and the script runs.

`NN` is a zero-padded sequence shared by the doc and its script (e.g. `00`, `01`). Reference example:
A1 → `docs/learn/00-tooling-and-skeleton.md` + `learn/00_config_demo.py`.

## How to use
- **Run every demo:** `uv run python learn/run_all.py` (or one at a time: `uv run python learn/NN_*.py`).
- One row per concept. Fill `doc`, `script`, `self-quiz` when each exists.
- `Status`: `not-started` → `in-progress` → `done`.
- Add a short `Takeaway` once learned — the thing you'd explain to a teammate.

## Slice A

| Concept | Task | Doc | Script | Self-quiz | Status | Takeaway |
|---|---|---|---|---|---|---|
| Tooling & skeleton (uv, pydantic-settings, FastAPI) | A1 | `docs/learn/00-tooling-and-skeleton.md` | `learn/00_config_demo.py` | in doc | **done** | Config is a typed, cached, server-side boundary that fails loudly on bad env vars. |
| API contract & validation (contract-first Pydantic) | A2 | `docs/learn/01-api-contract-and-validation.md` | `learn/01_schemas_demo.py` | in doc | **done** | Typed models first → validation + 422 for free; reserved-field envelope grows without breaking callers. |
| Embeddings & dimensions (provider registry) | A3 | `docs/learn/02-embeddings.md` | `learn/02_embeddings.py` | in doc | **done** | An `Embedder` protocol makes the provider swappable (Voyage default @ 1024, Gemini drop-in @ 768); `EMBED_DIM` is pinned to the active provider, so switching providers forces a full re-embed + re-index. |
| BM25 / sparse vectors | A4 | `docs/learn/03-bm25-sparse.md` | `learn/03_bm25_sparse.py` | in doc | **done** | BM25 gives the lexical half of hybrid retrieval — rare tokens like error codes get high IDF weight, catching exact-match queries that dense embeddings dilute across all dimensions. |
| Pinecone sparse-dense store (infra) | A5 | `docs/learn/_infra-A5-pinecone-store.md` | (live integration test) | in note | **done** | One dotproduct index holds dense+sparse; Pinecone metadata can't be null; ensure_index guards EMBED_DIM drift. |
| Kaggle ingest + normalize (infra) | A7 | `docs/learn/_infra-A7-ingest.md` | (tiny live ingest test) | in note | **done** | Deterministic content-hash ids make re-ingest idempotent; BM25 must be fit on the same capped corpus that gets embedded so vocabulary aligns at query time. |
| Hybrid fusion & normalization | A6 | `docs/learn/04-hybrid-fusion.md` | `learn/04_hybrid_fusion.py` | in doc | **done** | Scaling dense by alpha and sparse by (1-alpha) before the dotproduct query is the fusion — the linear metric means vector scaling is score scaling. |
| Blended confidence (v0) | A8 | `docs/learn/05-confidence-v0.md` | `learn/05_confidence_v0.py` | in doc | **done** | Blending retrieval agreement + sigmoid-scaled top-score gives an explainable, tunable confidence number that can be dashboarded and debugged — raw LLM self-confidence cannot. |
| README / run-it-yourself | A10 | top-level `README.md` | — | self-quizzes across all learn docs | **done** | A repo a stranger can clone, ingest, and query in five commands — and learn each concept from. |

> NN is assigned in artifact-creation order (A1→00, A2→01, …); doc and script share the same NN.

## Slice B
| Concept | Task | Doc | Script | Status | Takeaway |
|---|---|---|---|---|---|
| LangGraph state machines | B1 | `docs/learn/06-langgraph-state.md` | `learn/06_langgraph_state.py` | **done** | A node returns *what changed*; LangGraph merges partials and follows edges — control flow is explicit, inspectable structure. |
| Guarded-copilot pattern (answer/clarify/escalate) | B8 | `docs/learn/07-guarded-copilot.md` | `learn/07_guarded_copilot.py` | **done** | A guarded copilot escalates under uncertainty rather than hallucinating — confidence and SLA risk are deterministic, auditable numbers that drive a three-way route (answer/clarify/escalate), so control flow is inspectable and the LLM cannot bypass the safety net. |

## Slice C
| Concept | Task | Doc | Script | Status | Takeaway |
|---|---|---|---|---|---|
| LangSmith tracing / observability | C7 | `docs/learn/08-langsmith-tracing.md` | `learn/08_langsmith_tracing.py` | **done** | `@traceable` + `tracing_context` give free-with-a-flag observability — the same code path runs identically whether a LangSmith key is present or not, so tracing degrades to a no-op instead of becoming a hard dependency, and wrapping the raw LLM client (not just the graph) is what puts actual prompts and completions inside the trace. |
| In-app explainability (`?explain=true`) | C8 | `docs/learn/09-explainability.md` | `learn/09_explainability.py` | **done** | Explainability is a self-contained, in-app accumulator (`reasoning` + confidence/SLA breakdowns) built from the same deterministic functions the graph already runs — so `?explain=true` shows the exact arithmetic behind a decision without depending on LangSmith or making any extra calls. |

## Bonus / synthesis (cross-slice)
| Concept | Task | Doc | Script | Status | Takeaway |
|---|---|---|---|---|---|
| From classic RAG to a guarded agentic copilot (+ calibration) | overview | `docs/learn/10-rag-to-guarded-copilot.md` (+ interactive `docs/learn/10-rag-to-guarded-copilot.html`) | `learn/10_calibration_demo.py` | **done** | The step up from classic RAG is *calibration*: never trust the LLM's self-reported confidence (it's overconfident); instead blend observable signals (neighbour agreement, retrieval closeness, LLM/majority consistency, missing-info penalty) into a score that actually tracks accuracy, then route answer/clarify/escalate on it. The interactive HTML lets you drag the signals and watch the decision move. |

## Slice D
| Concept | Task | Doc | Script | Status | Takeaway |
|---|---|---|---|---|---|
| Offline vs online eval | D11 | `docs/learn/11-eval.md` | `learn/11_eval.py` | **done** | Offline eval is a reproducible, pre-deploy gate — fixed target, fixed dataset, deterministic evaluators, same numbers every run — while online eval grades real production traffic and human feedback post-deploy; QueuePilot runs both (`eval/run_experiment.py` + `eval/run_online.py` + `POST /feedback`) because each sees a failure mode the other structurally cannot. |
| Building an eval dataset | D12 | `docs/learn/12-eval-datasets.md` | `learn/12_eval_datasets.py` | **done** | A held-out split only earns the word "held-out" when leakage is checked by assertion, not assumed by convention — QueuePilot samples strictly from records beyond the indexing cap, stratifies by label, hand-injects edge cases, and fails loudly the instant an eval id turns up in the indexed set. |

## Slice E
| Concept | Task | Doc | Script | Status | Takeaway |
|---|---|---|---|---|---|
| Containerization (Docker, multi-stage, local run) | E3 | `docs/learn/13-containerization.md` | `learn/13_containerization.py` | **done** | A multi-stage Dockerfile builds the React bundle in a throwaway Node stage and ships a lean Python runtime that copies just the built `dist` — cache by copying dependency manifests before source, bind `0.0.0.0` so the port is reachable outside the container, respect `$PORT`, and inject `.env` at run time (never bake secrets into a layer) so one image runs identically locally and on Render. |
| Securing a public API (invite cookie, rate limit, daily cap) | E7 | `docs/learn/14-securing-a-public-api.md` | `learn/14_securing_a_public_api.py` | **done** | A signed, HttpOnly, SameSite=Lax cookie (stdlib HMAC + `hmac.compare_digest`) proves "this browser knows the invite code" without a session store or a new dependency, every gate degrades to open when its env var is unset, and a per-IP rate limit plus a global daily cap are two independent guards — one client hammering the API vs. many clients draining the shared provider budget. |

## Slice F
| Concept | Task | Doc | Script | Status | Takeaway |
|---|---|---|---|---|---|
| REST vs GraphQL — additive API design (where each fits) | F7 | `docs/learn/15-graphql.md` | `learn/15_graphql.py` | **done** | GraphQL lets the client declare the response shape against one typed schema; it's a second adapter over the same service, so it wins on client-shaped payloads + an introspectable contract but not on backend compute — hence the deliberate split: GraphQL for the read/analysis surface, REST for liveness, cookie-auth, and best-effort writes. |

## Open questions / things I got stuck on
_(log friction here as you go — great material to revisit)_
