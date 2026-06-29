# QueuePilot — Project Roadmap (Slices A–E)

**Date:** 2026-06-29
**Status:** Living roadmap. Slice A is fully specced separately; B–E are intentionally
lightweight here and get their own spec → plan → build cycle when started.

---

## Why this exists

QueuePilot is too large for one spec. It is a semi-public, portfolio-first **agentic AI ticketing
system** built to (a) close concrete skill gaps for an *AI Developer (LLM & API Focus)* role and
(b) serve as a **learning vehicle**. Each slice is independently buildable and verifiable, and each
ships its own learning artifacts (the learning layer is a core graded requirement, not polish).

## One-paragraph product

A user submits a support ticket; QueuePilot classifies it, retrieves similar historical cases via
hybrid retrieval, scores sentiment / SLA risk / confidence, recommends queue and priority, asks a
clarifying question when info is missing, decides on escalation, and drafts a grounded suggested
reply — behaving as a **conservative support copilot**, not a generic chatbot. Every run is traced
and evaluable.

## Locked stack decisions

- **FastAPI** app shell (serves API + minimal dashboard in v1).
- **Pinecone** single **sparse-dense** index; **Gemini** dense embeddings + **BM25 (`pinecone-text`)**
  sparse; `hybrid_score_norm(alpha)` fusion.
- **LangGraph** for the workflow; **LangSmith** for tracing + offline/online eval.
- **Swappable LLM provider registry** (default cheap/fast; OpenAI a provable drop-in).
- **Lean posture:** Azure Service Bus, GraphQL, OpenAI-only, and voice are *deferred* — framed as
  transferable in interviews, not built in v1.
- Tooling: `uv`, Python 3.11+. Deploy target: Docker → Render.

---

## Slices

### Slice A — Foundation & Retrieval Loop  ✅ specced
FastAPI skeleton, Kaggle ingest+normalize, Gemini embeddings, Pinecone sparse-dense hybrid index,
plain `/analyze` baseline (majority-vote labels + confidence v0). **No LangGraph.**
Closes: Pinecone, hybrid RAG, FastAPI, Python, NLP extraction.
Spec: `2026-06-29-queuepilot-slice-a-design.md`.

### Slice B — Agentic Workflow
Replace `analyze/baseline.py` with a **LangGraph** state machine behind the same `/analyze`
contract: classify → retrieve → assess-missing-info → score → decide (answer / clarify / escalate)
→ draft grounded reply. Adds sentiment (frustration + negativity), SLA risk, escalation decision,
clarification questions, suggested reply. Extends confidence into the full blended score.
Closes: **LangGraph, LLM agent orchestration** (your biggest named gaps).
Learning: LangGraph state/transitions, guarded-copilot pattern.

### Slice C — Dashboard + Observability
Single-page operations console (input → result cards → suggested reply → similar-ticket evidence →
trace summary). **Opt-out `--explain` debug mode** exposing node-by-node *why*, retrieval scores,
confidence breakdown, live trace. **LangSmith** tracing wired into every run.
Closes: LangSmith (tracing), basic frontend.
Learning: tracing, in-app explainability.

### Slice D — Evaluation
LangSmith **offline** curated dataset eval, **online** eval on real traces, experiment comparison,
human-feedback path. Eval snapshot cards in the dashboard.
Closes: LangSmith eval/experiments.
Learning: offline vs online eval, building an eval dataset.

### Slice E — Deploy & Harden
Dockerize FastAPI; deploy to Render (same app serves UI + API); invite-code access (signed
HTTP-only cookie), rate limiting on `/analyze`, max input limits, logging.
Closes: cloud/deployment story.

---

## Deferred (explicitly NOT v1)

GraphQL · Azure / Azure Service Bus · OpenAI-only · voice (ASR/TTS) · full auth/user management ·
multi-tenant SaaS · message-bus complexity. These map to job "nice-to-haves" or "transferable"
talking points and would dilute the core hiring signal if built now.

## Job-requirement coverage map

| Job requirement | Slice | Status |
|---|---|---|
| Python (required) | A–E | ✅ |
| FastAPI | A | ✅ |
| LangGraph | B | ✅ |
| LangSmith | C, D | ✅ |
| OpenAI | provider registry (A+) | ✅ provable drop-in |
| Pinecone / vector DB | A | ✅ |
| RAG / hybrid retrieval | A | ✅ genuine hybrid |
| LLM agent orchestration | B | ✅ |
| API design | A–E | ✅ |
| NLP data extraction | A | ✅ ingest/normalize |
| Cloud infra | E | ✅ Render (AWS/Azure = transferable) |
| Frontend support | C | ✅ minimal dashboard |
| GraphQL | — | ⏸ deferred (transferable: REST) |
| Azure Service Bus (essential) | — | ⏸ deferred (transferable: Bull/Redis/Temporal) |
| ASR/TTS / voice | — | ⏸ deferred (v1.5+; transferable: Deepgram) |
