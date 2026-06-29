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
- One row per concept. Fill `doc`, `script`, `self-quiz` when each exists.
- `Status`: `not-started` → `in-progress` → `done`.
- Add a short `Takeaway` once learned — the thing you'd say in an interview.

## Slice A

| Concept | Task | Doc | Script | Self-quiz | Status | Takeaway |
|---|---|---|---|---|---|---|
| Tooling & skeleton (uv, pydantic-settings, FastAPI) | A1 | `docs/learn/00-tooling-and-skeleton.md` | `learn/00_config_demo.py` | in doc | **done** | Config is a typed, cached, server-side boundary that fails loudly on bad env vars. |
| API contract & validation (contract-first Pydantic) | A2 | `docs/learn/01-api-contract-and-validation.md` | `learn/01_schemas_demo.py` | in doc | **done** | Typed models first → validation + 422 for free; reserved-field envelope grows without breaking callers. |
| Embeddings & dimensions | A3 | `docs/learn/02-embeddings.md` | `learn/02_embeddings.py` | in doc | **done** | Pinning `EMBED_DIM=768` at ingest time is irreversible — the Matryoshka property lets you go smaller, but changing the index dimension requires a full re-embed + re-index. |
| BM25 / sparse vectors | A4 | `docs/learn/03-bm25-sparse.md` | `learn/03_bm25_sparse.py` | in doc | not-started | |
| Hybrid fusion & normalization | A6 | `docs/learn/04-hybrid-fusion.md` | `learn/04_hybrid_fusion.py` | in doc | not-started | |
| Blended confidence (v0) | A8 | `docs/learn/05-confidence-v0.md` | `learn/05_confidence_v0.py` | in doc | not-started | |
| README / run-it-yourself | A10 | top-level `README.md` | — | — | not-started | |

> NN is assigned in artifact-creation order (A1→00, A2→01, …); doc and script share the same NN.

## Slice B (seed — expand when started)
| Concept | Doc | Status |
|---|---|---|
| LangGraph state & transitions | `docs/learn/04-langgraph.md` | not-started |
| Guarded-copilot pattern (answer/clarify/escalate) | `docs/learn/05-guarded-copilot.md` | not-started |

## Slice C
| Concept | Doc | Status |
|---|---|---|
| LangSmith tracing | `docs/learn/06-tracing.md` | not-started |
| In-app explainability (`--explain`) | `docs/learn/07-explainability.md` | not-started |

## Slice D
| Concept | Doc | Status |
|---|---|---|
| Offline vs online eval | `docs/learn/08-eval.md` | not-started |
| Building an eval dataset | `docs/learn/09-eval-datasets.md` | not-started |

## Open questions / things I got stuck on
_(log friction here as you go — great interview material)_
