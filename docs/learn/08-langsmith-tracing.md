# 08 — LangSmith tracing / observability

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `C7` · Runnable companion: `uv run python learn/08_langsmith_tracing.py`

## 1. Concept

**Observability** for an agentic workflow means being able to answer "what actually happened inside
this run?" after the fact — which nodes ran, in what order, with what inputs/outputs, how long each
took, and where an LLM call sat in the tree. A plain `print`/log statement tells you a function ran;
it doesn't give you a navigable, timed, nested picture of a whole request.

**Distributed tracing** solves this by wrapping units of work (functions, LLM calls, chains) in
**spans** that form a **run tree**: a root span for the overall request, with child spans for each
node/call it makes. Each span records inputs, outputs, timing, and errors, and the whole tree is
shipped to a backend you can browse.

**LangSmith** is LangChain's hosted tracing backend, built for exactly this shape of workflow:

- `@traceable(...)` — a decorator that turns a plain function into a traced span. Call it on any
  function (not just LangChain/LangGraph constructs) and it becomes a node in the run tree.
- `tracing_context(enabled=...)` — a context manager that turns tracing on/off for the code inside
  it, without changing any call sites. When `enabled=False`, every `@traceable` inside becomes a
  no-op wrapper (near-zero overhead, nothing sent over the network).
- `get_current_run_tree()` — inside a traced function, returns the `RunTree` object for the
  *currently executing* span, so you can read its `id` / build its dashboard `url` for your own
  response payload.

## 2. In QueuePilot

- `app/providers/chat.py` — `GroqChat.complete` and `GroqChat.complete_json` are decorated with
  `@traceable(run_type="llm", name="GroqChat.complete"/"...complete_json")`. This is deliberate:
  LangGraph automatically traces its own nodes and edges, but it has no visibility into what a node
  does *inside* — a raw `Groq(...)` client call is invisible to LangSmith unless we wrap it
  ourselves. Wrapping the chat provider (not the LangGraph nodes) is what puts individual LLM calls
  — with their prompts, completions, and latency — into the run tree as children of each node span.
- `app/analyze/graph_analyzer.py::GraphAnalyzer.analyze` — the composition root for tracing:
  - Computes `tracing_enabled = bool(settings.langsmith_tracing and settings.langsmith_api_key)`.
  - Wraps the whole graph invocation in `@traceable(run_type="chain", name="GraphAnalyzer.analyze")`
    and runs it inside `with tracing_context(enabled=tracing_enabled): ...`.
  - Inside the traced function, calls `get_current_run_tree()` and stashes the result so it can be
    used after the `with` block closes (a run tree object read via `get_current_run_tree()` is only
    valid *while* the traced function is executing).
  - Feeds the captured run tree (or `None`), the measured `latency_ms`, `settings.langsmith_project`,
    and `tracing_enabled` into `app/analyze/trace.py::build_trace_summary(...)`, whose return value
    becomes `AnalyzeResponse.trace`.
- `app/analyze/trace.py::build_trace_summary` — a small pure function, intentionally separated from
  `graph_analyzer.py` so the run-id/url extraction logic is unit-testable with a fake run-tree-like
  object (see `tests/test_trace.py`) instead of a live LangSmith run. It never raises: any failure
  extracting `.id` or `.get_url()` falls back to a disabled-shaped result.
- The `trace` payload shape (`03-API-CONTRACT.md`, extended by `05-DECISIONS-LOCKED.md` D14):
  ```json
  {"enabled": false}
  ```
  when tracing is off/unavailable, or
  ```json
  {"enabled": true, "run_id": "...", "url": "https://smith.langchain.com/r/...", "latency_ms": 812.4, "project": "queuepilot"}
  ```
  when it ran. It is populated on **every** `/analyze` call once tracing is wired, independent of
  the separate `?explain=true` flag (see `09-explainability.md`).

## 3. Why this way

- **Graceful degradation by construction.** No `LANGSMITH_API_KEY` (e.g. local dev, CI, a fresh
  clone) means `tracing_enabled` is `False`, `tracing_context(enabled=False)` makes every
  `@traceable` call a no-op, and `build_trace_summary` returns `{"enabled": False}`. Nothing about
  `/analyze`'s behavior, latency, or response shape depends on LangSmith being configured — tracing
  is additive observability, never a hard dependency (`05-DECISIONS-LOCKED.md` D1's "lean" posture).
- **Why wrap the raw Groq client instead of relying on LangGraph's built-in tracing?** LangGraph
  already traces graph structure — which node ran, how long it took, what partial state it returned
  — for free. But a node's *internal* LLM call (prompt in, completion out, provider latency) is
  invisible to LangSmith unless something inside that call is itself traced. `@traceable` on
  `GroqChat.complete`/`complete_json` closes that gap: it makes the raw Groq API call a child span
  of whichever node called it, so a LangSmith trace shows the full picture — node timing *and*
  the LLM call nested inside it — not just the node boundary.
  Note that this doesn't apply to `full_confidence_breakdown`/`sla_risk_breakdown` in `score` — that
  node is deterministic (no LLM, no I/O), so there's nothing hidden inside it that tracing would add;
  its numbers are made visible instead through the `--explain` accumulator (`09-explainability.md`).
- **Why capture the run tree via `get_current_run_tree()` instead of threading it through as a
  parameter?** The run tree only exists for the lifetime of the traced call; grabbing it *inside*
  `_run()` (the `@traceable`-decorated closure) is the only place it's guaranteed to be the tree for
  *this specific request*, not a stale one from a previous call or a different worker.
- **Why a separate `trace.py` module instead of building the dict inline in `graph_analyzer.py`?**
  Testability: `build_trace_summary` takes primitives and a fake run-tree object, so
  `tests/test_trace.py` covers "url raises", "no `.id` attribute", "run tree is `None`" — all without
  a live LangSmith run or network call.

## 4. Verify it yourself

```bash
uv run python learn/08_langsmith_tracing.py
```

**Expected:** No network call and no `LANGSMITH_API_KEY` required. The script demonstrates two
things: (1) `tracing_context(enabled=False)` around a tiny `@traceable` function proves tracing is a
true no-op when disabled — the function still runs and returns its value, but produces no run tree
to read; and (2) `build_trace_summary` is called with a fake run-tree object (mirroring
`tests/test_trace.py`'s `_FakeRunTree`) to show the exact disabled-vs-enabled shape that becomes
`AnalyzeResponse.trace` in production, including the never-raises guarantee when `.get_url()` blows up.

## 5. Self-quiz

1. If `LANGSMITH_API_KEY` is unset in `.env`, what does `AnalyzeResponse.trace` look like, and what
   code path guarantees that?
2. Why is `@traceable` applied to `GroqChat.complete`/`complete_json` rather than only relying on
   LangGraph's automatic node/edge tracing?
3. Why does `build_trace_summary` catch exceptions around `.id` and `.get_url()` instead of letting
   them propagate?

<details><summary>Answers</summary>

1. `{"enabled": false}`. `GraphAnalyzer.analyze` computes
   `tracing_enabled = bool(settings.langsmith_tracing and settings.langsmith_api_key)`, which is
   `False` with no key; `tracing_context(enabled=False)` no-ops every `@traceable` call, and
   `build_trace_summary(..., enabled=False)` short-circuits to the minimal disabled shape before
   touching the run tree at all.
2. LangGraph traces the *structure* of the graph (which node ran, how long the node took) but has no
   visibility into what happens *inside* a node's own function body. The actual Groq API call —
   prompt, completion, provider latency — is invisible to LangSmith unless it is itself wrapped in
   `@traceable`, so wrapping the chat client is what nests LLM calls under their owning node in the
   trace.
3. `build_trace_summary` feeds `AnalyzeResponse.trace`, which must never break `/analyze`. A
   third-party object's `.id` property or `.get_url()` method could raise for reasons entirely
   unrelated to the actual ticket-analysis work (e.g. a LangSmith SDK internal error), so every
   extraction is wrapped and falls back to `None` rather than turning an observability nicety into a
   500 error.

</details>

## 6. Takeaway

"`@traceable` + `tracing_context` give free-with-a-flag observability — the same code path runs
identically whether a LangSmith key is present or not, so tracing degrades to a no-op instead of
becoming a hard dependency, and wrapping the raw LLM client (not just the graph) is what puts actual
prompts and completions inside the trace."
