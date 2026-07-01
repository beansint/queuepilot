# QueuePilot

[![CI](https://github.com/beansint/queuepilot/actions/workflows/ci.yml/badge.svg)](https://github.com/beansint/queuepilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

An **agentic AI ticketing system** for IT/helpdesk support: paste a ticket and get back a routed
queue, priority, similar historical cases, and a confidence score — built on **hybrid retrieval**
(dense + sparse) over a real support-ticket corpus, with a guarded "support copilot" workflow.

> **Status:** Slices A (Foundation & Retrieval Loop) and B (Agentic Workflow) complete — `/analyze` is
> driven by a LangGraph state machine over hybrid retrieval on 3,000 real tickets. Slice C
> (Dashboard + Observability) is **in progress**: LangSmith tracing and the opt-out `--explain` debug
> mode are landing on the backend now; the single-page console is designed (Vite + React + Tailwind +
> shadcn, served by this same FastAPI app) but its **build is paused pending a UI-design session** —
> no dashboard yet. Evaluation and deployment land in Slices D–E (see [Roadmap](#roadmap)).

It's also a **learning project**: every component ships a concept doc + runnable script + self-quiz
(see [The learning layer](#the-learning-layer)).

---

## What it does (Slice A)

`POST /analyze` with ticket text → a structured, forward-compatible envelope:

```bash
curl -s -X POST localhost:8000/analyze -H 'Content-Type: application/json' \
  -d '{"text":"I was charged twice for my subscription this month and need a refund"}'
```
```jsonc
{
  "category": "Incident",
  "queue": "Billing and Payments",
  "priority": "low",
  "confidence": 0.841,                 // blended: retrieval agreement + bounded top score
  "similar_tickets": [                 // real neighbors from the corpus, hybrid-ranked
    {"score": 0.42, "queue": "Billing and Payments", "snippet": "..."},
    {"score": 0.41, "queue": "Billing and Payments", "snippet": "..."}
  ],
  "sentiment": null, "sla_risk": null, "escalate": null,   // reserved for Slice B
  "clarification": null, "suggested_reply": null, "trace": null
}
```

A unanimous neighborhood (above) yields **high confidence**; a mixed one yields lower confidence —
the score is explainable and tunable, never raw LLM self-confidence.

## Architecture

```
POST /analyze ─► app/analyze/baseline.py (Analyzer)
                   │  embed_query (Voyage)  +  encode_query (BM25)
                   │  └─► hybrid_score_norm(alpha)         # weight semantic vs lexical
                   │       └─► PineconeStore.hybrid_query  # one dotproduct index, dense+sparse
                   │            └─► majority-vote labels + confidence v0
                   └─► AnalyzeResponse (binding contract)
```

- **Hybrid retrieval** — dense (Voyage `voyage-3.5-lite`, 1024d) for meaning + sparse (BM25) for
  exact keywords, fused in a single Pinecone dotproduct index with an alpha weight.
- **Provider registry** — embeddings sit behind an `Embedder` protocol; swap Voyage / Gemini / (next)
  OpenAI with one env var (`EMBEDDING_PROVIDER`).
- **Contract-first** — the `AnalyzeResponse` envelope is fixed from day one; later slices fill
  reserved fields without breaking the API.
- **Designed for the graph** — `Analyzer` is the one place that composes embed+retrieve+derive, so
  Slice B drops in a LangGraph runtime behind the same `/analyze` contract.

Canonical design docs live in [`docs/final-build-plan/`](docs/final-build-plan/) (start with its
`README.md`).

## Stack

FastAPI · LangGraph (guarded copilot workflow) · Pinecone (sparse-dense hybrid) · Voyage embeddings
(registry-swappable) · `pinecone-text` BM25 · Groq chat (registry-swappable) · Pydantic · `uv` ·
ruff + mypy(strict) + pytest · GitHub Actions CI. **LangSmith tracing is now active** (Slice C);
offline/online eval expands it further in Slice D. The Slice C console (Vite + React + Tailwind +
shadcn, served by this app) is designed but its build is paused pending a UI-design session.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync                                   # install deps into .venv
cp .env.example .env                      # then fill in keys (see below)

uv run python data/download.py            # fetch the Kaggle corpus into data/raw/ (needs Kaggle token)
uv run python data/ingest.py              # normalize → embed → BM25 → upsert ~3k tickets to Pinecone
                                          #   paid tier? add:  --rpm 5000 --batch 100   (skips throttle)

uv run uvicorn app.main:app --reload      # serve the API at http://localhost:8000
#   GET  /health     • POST /analyze     • POST /analyze?explain=true
```

**Keys** (`.env`, server-side only — see `.env.example`):
`VOYAGE_API_KEY` (embeddings; 200M free tokens) · `PINECONE_API_KEY` · `KAGGLE_USERNAME`/`KAGGLE_KEY`
(dataset download). `EMBEDDING_PROVIDER=voyage` by default; set `gemini` (+ `GEMINI_API_KEY`,
`EMBED_DIM=768`) to swap.

**Develop:**
```bash
uv run pytest -q                # unit tests (live integration is gated, see below)
uv run ruff check . && uv run mypy app tests learn data
QUEUEPILOT_RUN_INTEGRATION=1 uv run pytest -m integration   # live: real Voyage + Pinecone
```

## Observability & `--explain`

Every `/analyze` call carries a `trace` summary; passing `?explain=true` also fills a `debug`
reasoning trail — both are additive fields on the existing envelope, `null`/no-op when unused.

```bash
# enable LangSmith tracing (server-side only; omit to run fully offline — trace.enabled: false)
export LANGSMITH_API_KEY=...
export LANGSMITH_PROJECT=queuepilot   # optional, defaults per LangSmith config

# opt-out debug mode: adds an in-app step-by-step reasoning trail to the response
curl -s -X POST 'localhost:8000/analyze?explain=true' -H 'Content-Type: application/json' \
  -d '{"text":"I was charged twice for my subscription this month and need a refund"}'
```
```jsonc
{
  // ...category / queue / priority / confidence / similar_tickets / sentiment / etc. as usual...
  "trace": {"enabled": true, "run_id": "...", "url": "https://smith.langchain.com/...", "latency_ms": 842.3, "project": "queuepilot"},
  "debug": {"steps": [{"node": "retrieve", "summary": "...", "data": {}}, "..."]}
}
```
Without `?explain=true`, `debug` stays `null`. Without a LangSmith key, `trace.enabled` is `false`
and the rest of `trace` is `null` — no external calls, no error. See
[`docs/final-build-plan/09-SLICE-C-DESIGN.md`](docs/final-build-plan/09-SLICE-C-DESIGN.md) for the
full design.

## The learning layer

A core part of this project: every concept ships a doc + a standalone runnable script + a self-quiz,
logged in [`docs/final-build-plan/LEARNING-LOG.md`](docs/final-build-plan/LEARNING-LOG.md).

```bash
uv run python learn/run_all.py            # run every concept demo, in build order
# …or one at a time:
uv run python learn/02_embeddings.py      # embeddings & cosine similarity
uv run python learn/04_hybrid_fusion.py   # alpha-weighted dense+sparse fusion
uv run python learn/06_langgraph_state.py # LangGraph state merge
uv run python learn/07_guarded_copilot.py # answer / clarify / escalate routing
```
Read the matching `docs/learn/NN-*.md` (with its self-quiz) alongside each demo.
(`02_embeddings.py` makes a live Voyage call; the rest run offline.)

## Roadmap

| Slice | Scope | Status |
|---|---|---|
| **A — Foundation & Retrieval Loop** | hybrid retrieval + baseline `/analyze` | ✅ done |
| **B — Agentic Workflow** | LangGraph state machine (classify → assess → score → decide → draft) | ✅ done |
| **C — Dashboard + Observability** | LangSmith tracing + `--explain` (backend) landing; console designed, build paused pending UI-design session | 🚧 in progress |
| **D — Evaluation** | LangSmith offline + online eval | planned |
| **E — Deploy & Harden** | Docker → Render, invite-code auth, rate limiting | planned |

## Dataset & license

Code is **[MIT](LICENSE)**. The retrieval corpus is the *"Customer IT Support — Multilingual Ticket
Dataset"* by **tobiasbueck** on Kaggle, licensed **CC BY 4.0** — not redistributed here; see
[`docs/final-build-plan/07-DATASET.md`](docs/final-build-plan/07-DATASET.md) for attribution and how
to obtain it.
