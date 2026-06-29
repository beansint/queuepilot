# QueuePilot — Build Plan Overview

**Purpose:** the actionable build plan. Where the `docs/superpowers/specs/` files explain *what and
why* (design), these `docs/build-plans/` files are the *how and in what order* (executable tasks
that map 1:1 to GitHub + Linear issues).

---

## Repo strategy

| Repo | Visibility | Role |
|---|---|---|
| `queuepilot` | **Private now → public at end of Slice A** | Flagship portfolio repo. Clean `main`, one feature branch + PR per slice. Public history must read as deliberate. |
| `queuepilot-lab` | **Private (permanent)** | Sandbox: alpha sweeps, embedding-model comparisons, eval-harness prototypes, dataset EDA. Keeps the flagship clean. |

**Branch/PR workflow (flagship):**
- `main` stays presentable at all times.
- One branch per slice: `slice-a-foundation`, `slice-b-workflow`, …
- Task-sized commits with clear messages; squash-merge each slice via PR.
- Flip `queuepilot` to public once Slice A demonstrates working hybrid retrieval.

## Milestone ↔ slice map

| Milestone | Slice | Outcome |
|---|---|---|
| **M-A** | Foundation & Retrieval Loop | `POST /analyze` returns category/queue/priority + hybrid-retrieved neighbors + confidence v0. No LangGraph. |
| **M-B** | Agentic Workflow | LangGraph state machine: classify→retrieve→assess→score→decide→draft. Full output envelope. |
| **M-C** | Dashboard + Observability | Single-page console + opt-out `--explain` debug mode + LangSmith tracing. |
| **M-D** | Evaluation | LangSmith offline + online eval, experiments, feedback path. |
| **M-E** | Deploy & Harden | Docker → Render, invite-code auth, rate limiting. |

## Learning layer (core graded requirement, every slice)

1. `docs/learn/NN-topic.md` — annotated concept doc per phase.
2. `learn/NN_*.py` — runnable concept script (one concept in isolation).
3. End-of-phase checkpoint + self-quiz.
4. Opt-out in-app `--explain` debug mode (lands in Slice C).

## Source-of-truth docs

- Design (why/what): `docs/superpowers/specs/2026-06-29-queuepilot-slice-a-design.md`
- Roadmap: `docs/superpowers/specs/2026-06-29-queuepilot-roadmap.md`
- Build plans (how): `docs/build-plans/slice-a.md`, `docs/build-plans/slices-b-e.md`
