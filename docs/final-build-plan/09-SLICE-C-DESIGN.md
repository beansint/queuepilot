# 09 — Slice C Design: Dashboard + Observability

Approved design pass for Milestone **M-C**. Build order maps to the C1–C9 outline on epic
`BEA-139` / GitHub #12.

## Purpose
Give the guarded copilot a face and a flight recorder: a single-page console for exercising
`/analyze` by hand, an opt-out `--explain` debug mode that surfaces *why* the graph decided what it
decided, and opt-in LangSmith tracing (`LANGSMITH_TRACING=true` + an API key) — all behind the same
`03-API-CONTRACT.md` envelope.

## Frontend
**Choice (D13):** Vite + React + TypeScript + Tailwind + shadcn/ui, built to static assets and
**served by the same FastAPI app** — no separate host, no separate origin. This preserves D10's
single-Render-container deploy story and keeps the console same-origin with the API, which Slice E's
signed HTTP-only cookie auth depends on (cross-origin cookies would need extra CORS/`SameSite` work
we don't want to carry).

**Status: build paused pending a UI-design session.** The decision/direction is locked; the actual
component work (C5, and the UI-wiring half of C6) does not start until that design pass happens.
Backend surfaces for Slice C (tracing, `--explain`) are not blocked by this and proceed independently.

## Tracing
LangSmith tracing is **active only when both `LANGSMITH_TRACING=true` AND a `LANGSMITH_API_KEY` are
set** — it is not live on every call by default. When both are configured, the `GraphAnalyzer.analyze`
call (and, via `@traceable`, the underlying graph-node/LLM calls) is traced and shows up as a run in
the LangSmith UI. "Live in the demo" means setting both env vars before starting the server.

**Graceful no-op:** if tracing is off (either var unset/false), the endpoint behaves exactly as
before — `@traceable`/`tracing_context` become pass-throughs and the response's `trace` field is
`{"enabled": false}`. No error, no latency penalty beyond the wrapped call itself.

`trace` payload shape (unchanged from `03-API-CONTRACT.md`'s reservation, now filled):
```python
trace: dict | None = {
    "enabled": bool,        # False when no LangSmith key configured
    "run_id": str | None,   # LangSmith run id (None if disabled)
    "url": str | None,      # deep link to the run in the LangSmith UI (None if disabled)
    "latency_ms": float,    # wall-clock time for the whole /analyze call
    "project": str | None,  # LangSmith project name (None if disabled)
}
```

## Explain mode
**Choice:** opt-out via an HTTP query param on the existing endpoint — `POST /analyze?explain=true`.
Default (`explain` absent or `false`) behaves exactly as Slice B; no shape change for existing callers.

**Data source:** an in-app accumulator on `TicketState` (not a second LangSmith read-path). Each
graph node appends a small structured note as it runs — e.g. which neighbors were retrieved and their
scores, the raw classification vote, the sentiment scores, the confidence sub-terms, the decide-router
branch taken and why. This keeps `--explain` **offline-testable** (works with a mocked chat model, no
live LangSmith needed) and decoupled from whether tracing is enabled.

`debug` payload shape (new field, null unless `?explain=true`):
```python
debug: dict | None = {
    "nodes": list[dict],       # one entry per graph node that recorded reasoning, in run order
    # each entry: {"name": str, "rationale": str}
    "retrieval": list[dict],   # one entry per retrieved neighbor
    # each entry: {"score": float, "queue": str, "priority": str, "type": str, "snippet": str}
    "confidence_breakdown": dict,  # full_confidence_breakdown(...) intermediate terms
    "sla_breakdown": dict,         # sla_risk_breakdown(...) intermediate terms
    "decision": str,               # decide-router branch taken (e.g. "answer" / "clarify" / "escalate")
}
```

## Envelope mapping
`03-API-CONTRACT.md`'s reserved `trace` field is now populated on every call, independent of
`--explain` — its `enabled` flag reflects whether tracing is actually configured (see Tracing
above), and is `{"enabled": false}` when it isn't. The new `debug` field (D14) is populated only
when `?explain=true` is passed, from the `TicketState` accumulator, and stays `None` otherwise.
Both are strictly additive — no existing field changes shape or meaning. **No API break.**

## Build order
- **C1** LangSmith wiring: env-driven client init, `@traceable` on the chat-model registry calls,
  graceful no-op without a key.
- **C2** `trace` payload assembly: run id / URL / latency / project, wired into the `/analyze` response.
- **C3** `TicketState` accumulator: each graph node appends a `{node, summary, data}` step.
- **C4** `?explain` query param on `POST /analyze`; `debug` field populated from the accumulator,
  `None` otherwise.
- **C5** ⏸️ *paused (UI-design hold)* — Vite/React/Tailwind/shadcn scaffold, built to static assets.
- **C6** FastAPI static-asset mount for the built console — **backend wiring only** ships now; the
  UI half that actually renders results ⏸️ *paused (UI-design hold)*.
- **C7** 📚 tracing concept doc + runnable script + self-quiz (`docs/learn/08-langsmith-tracing.md` /
  `learn/08_langsmith_tracing.py` — LEARNING-LOG already reserves these slots).
- **C8** 📚 explainability concept doc + runnable script + self-quiz
  (`docs/learn/09-explainability.md` / `learn/09_explainability.py`).
- **C9** tests: `trace` no-op path, `debug` populated/absent paths, mocked-chat offline coverage +
  gated live LangSmith integration test.

## Constraints
- Same HTTP contract: `POST /analyze` keeps its existing request/response shape; `trace` and `debug`
  are backward-compatible additions, never repurposed fields (per `03`'s invariant).
- Graceful degradation: no LangSmith key → `trace.enabled = false`, everything else unaffected; no
  `?explain` → `debug = null`.
- Offline-testable: `--explain` accumulator works with a mocked chat model; tracing wrapper is a
  no-op without a key, so the full test suite runs with zero external calls except the one gated
  live integration test.
- Console build is paused; nothing in this slice may claim the dashboard is shipped until C5/C6-UI
  resume after the UI-design session.
