# QueuePilot

[![CI](https://github.com/beansint/queuepilot/actions/workflows/ci.yml/badge.svg)](https://github.com/beansint/queuepilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

An **agentic AI ticketing system** for IT/helpdesk support: paste a ticket and get back a routed
queue, priority, similar historical cases, and a confidence score — built on **hybrid retrieval**
(dense + sparse) over a real support-ticket corpus, with a guarded "support copilot" workflow.

> **Status:** Slice A (Foundation & Retrieval Loop) complete — a working hybrid-retrieval `/analyze`
> API over 3,000 real tickets. The agentic LangGraph workflow, dashboard, evaluation, and deployment
> land in Slices B–E (see [Roadmap](#roadmap)).

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

FastAPI · Pinecone (sparse-dense hybrid) · Voyage embeddings (registry-swappable) ·
`pinecone-text` BM25 · Pydantic · `uv` · ruff + mypy(strict) + pytest · GitHub Actions CI.
LangGraph + LangSmith arrive in Slices B–D.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync                                   # install deps into .venv
cp .env.example .env                      # then fill in keys (see below)

uv run python data/download.py            # fetch the Kaggle corpus into data/raw/ (needs Kaggle token)
uv run python data/ingest.py              # normalize → embed → BM25 → upsert ~3k tickets to Pinecone
                                          #   paid tier? add:  --rpm 5000 --batch 100   (skips throttle)

uv run uvicorn app.main:app --reload      # serve the API at http://localhost:8000
#   GET  /health     • POST /analyze
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

## The learning layer

A core part of this project: every concept ships a doc + a standalone runnable script + a self-quiz,
logged in [`docs/final-build-plan/LEARNING-LOG.md`](docs/final-build-plan/LEARNING-LOG.md). Run any in
isolation:

```bash
uv run python learn/02_embeddings.py      # embeddings & cosine similarity
uv run python learn/03_bm25_sparse.py     # BM25 sparse vectors & IDF
uv run python learn/04_hybrid_fusion.py   # alpha-weighted dense+sparse fusion
uv run python learn/05_confidence_v0.py   # blended confidence
```
Concept docs: [`docs/learn/`](docs/learn/).

## Roadmap

| Slice | Scope | Status |
|---|---|---|
| **A — Foundation & Retrieval Loop** | hybrid retrieval + baseline `/analyze` | ✅ done |
| **B — Agentic Workflow** | LangGraph state machine (classify → assess → score → decide → draft) | planned |
| **C — Dashboard + Observability** | single-page console + `--explain` + LangSmith tracing | planned |
| **D — Evaluation** | LangSmith offline + online eval | planned |
| **E — Deploy & Harden** | Docker → Render, invite-code auth, rate limiting | planned |

## Dataset & license

Code is **[MIT](LICENSE)**. The retrieval corpus is the *"Customer IT Support — Multilingual Ticket
Dataset"* by **tobiasbueck** on Kaggle, licensed **CC BY 4.0** — not redistributed here; see
[`docs/final-build-plan/07-DATASET.md`](docs/final-build-plan/07-DATASET.md) for attribution and how
to obtain it.
