# AGENTS.md — QueuePilot

**Start here.** This file orients any AI agent or new contributor working on QueuePilot.

## What this is
A semi-public, portfolio-first **agentic AI ticketing system** (FastAPI + LangGraph + Pinecone
hybrid retrieval + LangSmith). It is also a **learning vehicle** — the learning layer is a graded
requirement, not optional.

## Canonical docs — read before coding
The single source of truth is **`docs/final-build-plan/`**. Read in this order:

1. `00-MASTER-SPEC.md` — product, outputs, philosophy
2. `01-TECH-STACK-LOCKED.md` 🔒 — the stack
3. `05-DECISIONS-LOCKED.md` 🔒 — decisions already made (do **not** relitigate)
4. `02-DATA-MODEL.md` 🔒 — Pinecone index + record shapes
5. `03-API-CONTRACT.md` 🔒 — the binding `/analyze` contract
6. `06-ARCHITECTURE.md` — module boundaries + data flow
7. `04-BUILD-SEQUENCE.md` — tasks ↔ issues
8. `LEARNING-LOG.md` — update as you build

Design *history* (immutable) lives in `docs/superpowers/specs/`.

## Non-negotiable rules
1. **Respect 🔒 locked docs.** Changes need user sign-off + a new `05-DECISIONS-LOCKED.md` entry.
2. **The API contract and data model are binding.** Conform code to them; if one looks wrong, stop
   and raise it — don't silently diverge.
3. **Learning layer is mandatory (repeatable pattern).** Any task that touches a concept ships a
   concept doc (copy `docs/learn/_TEMPLATE.md`) + a runnable script (copy `learn/_template.py`,
   runs via `uv run python learn/NN_<slug>.py`) + a self-quiz, and a `done` row in
   `docs/final-build-plan/LEARNING-LOG.md`. The pattern is defined once in LEARNING-LOG → "The
   repeatable pattern"; follow it every time. No artifacts + log row = task not done.
   Reference example: A1 → `docs/learn/00-tooling-and-skeleton.md` + `learn/00_config_demo.py`.
4. **Branch + PR per slice.** Keep `main` presentable (the repo goes public after Slice A).
5. **Verify honestly.** State what ran vs. N/A; never round "renders" up to "verified".

## Trackers
GitHub `beansint/queuepilot` and Linear project `QueuePilot` (team Devs) mirror 1:1.
Milestones = slices M-A…M-E. Current focus: **Slice A** (start at task A1).

## Build & run (placeholders until Slice A lands)
- `uv sync` — install deps (Python 3.11+)
- `uv run uvicorn app.main:app --reload` — run the API
- `uv run python data/ingest.py` — one-time corpus ingest
- `uv run python learn/01_embeddings.py` — run a concept script
- `uv run pytest` — tests
