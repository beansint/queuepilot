# 09 — In-app explainability (`?explain=true`)

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `C8` · Runnable companion: `uv run python learn/09_explainability.py`

## 1. Concept

**Explainability** here means: when a pipeline hands back a single number (a confidence score, a
routing decision), can you also show *why* — the intermediate signals that were combined, and how
much each one contributed? A black-box score ("confidence: 0.82") invites blind trust or blind
distrust; a decomposed score ("0.82 = 0.5·agreement(1.0) + 0.3·sigmoid(top_score)(0.55) + 0.2·
consistency(1.0) − 0.15·penalty(0.0)") lets a human — or a debugging session — check whether the
number is reasonable, spot a miscalibrated weight, and explain a specific decision in a post-mortem
("we escalated ticket #123 because agreement was 0.2, not because of SLA risk").

This is distinct from *tracing* (see `08-langsmith-tracing.md`): tracing tells you *what ran and how
long it took*; explainability tells you *what the pipeline concluded and the arithmetic behind it*.
They also have different availability requirements — a support engineer debugging a single ticket in
a demo/offline environment needs the reasoning trail regardless of whether a LangSmith key is
configured.

## 2. In QueuePilot

- `POST /analyze?explain=true` (`app/main.py`) — a query parameter that, when true, tells
  `GraphAnalyzer.analyze` to populate `AnalyzeResponse.debug` (`None` otherwise). It never touches
  LangSmith; it only reads state the graph already produced.
- `app/analyze/graph.py::TicketState` — three fields exist purely to *accumulate* explanations as the
  graph runs, in addition to the fields nodes normally set:
  ```python
  reasoning: dict[str, str]            # {node_name: one-line rationale}, merged node-by-node
  confidence_breakdown: dict[str, Any] # every intermediate term behind `confidence`
  sla_breakdown: dict[str, Any]        # every intermediate term behind `sla_risk`
  ```
  `reasoning` is written by *every* LLM-touching node (`classify`, `sentiment`, `assess_missing`,
  `score`, `draft_reply`, `clarify`) via a shared helper, `_with_reasoning(state, node, rationale)`,
  which reads the existing dict off state and returns the merged copy — necessary because LangGraph
  overwrites state *by key*, so returning a bare `{"reasoning": {"score": "..."}}` from the `score`
  node would silently erase what `classify` and `sentiment` already wrote.
- `app/analyze/scoring.py::full_confidence_breakdown` / `sla_risk_breakdown` — the deterministic
  `score` node (B7) calls these instead of the plain `full_confidence`/`sla_risk` functions. They run
  the *identical* formula but return every intermediate term instead of just the final float, so
  nothing about the production score computation changes — you're looking at the same numbers, just
  unpacked:
  ```python
  full_confidence_breakdown(top_score, agreement, llm_queue, majority_queue, missing_count) -> {
      "agreement", "top_score", "sigmoid_top_score", "consistency", "penalty", "final",
      "w_agreement", "w_score", "w_consistency", "penalty_missing",
  }
  sla_risk_breakdown(priority, frustration, has_missing) -> {
      "priority", "priority_weight", "frustration", "has_missing", "final",
      "w_priority", "w_frustration", "w_missing",
  }
  ```
- `app/analyze/graph_analyzer.py::GraphAnalyzer._build_debug(state, neighbors)` — a pure mapping (no
  LLM, no LangSmith) that assembles the final `debug` payload from the finished `TicketState`:
  ```python
  {
      "nodes": [{"name": ..., "rationale": ...}, ...],   # from state["reasoning"]
      "retrieval": [{"score", "queue", "priority", "type", "snippet"}, ...],  # from neighbors
      "confidence_breakdown": {...},   # state["confidence_breakdown"], verbatim
      "sla_breakdown": {...},          # state["sla_breakdown"], verbatim
      "decision": state["decision"],   # "answer" | "clarify" | "escalate"
  }
  ```

## 3. Why this way

- **In-app accumulator vs. reconstructing from LangSmith.** LangSmith traces already contain every
  node's inputs/outputs, so in principle you could reconstruct "what happened" by querying the
  LangSmith API after the fact. We didn't do that (`05-DECISIONS-LOCKED.md` D14): `debug` must work
  with **zero LangSmith key** — a developer running fully offline, or a demo environment without a
  configured API key, still gets the full reasoning trail. Coupling explainability to tracing
  infrastructure would make a core, graded requirement (the learning layer / D5) depend on an
  optional third-party service.
- **Why not fold `debug` into `trace`?** They answer different questions for different audiences.
  `trace` answers "is this call observable in LangSmith, and where" (an ops/debugging question,
  populated on *every* call once tracing is wired). `debug` answers "why did the pipeline decide
  this" (a product/support-agent question, populated only on request via `?explain=true`, and
  potentially large — full breakdowns and per-node rationale for every LLM call — so it's opt-in
  rather than sent on every response. `debug` is a new, separate reserved field, so existing
  `trace: dict | None` callers see no shape change (`03-API-CONTRACT.md`'s additive-only envelope
  philosophy).
- **Why sibling breakdown functions instead of changing `full_confidence`/`sla_risk`'s return type?**
  `full_confidence`/`sla_risk` already have callers and tests expecting a plain `float`. Adding
  `full_confidence_breakdown`/`sla_risk_breakdown` as siblings that compute the *same* formula but
  return every term keeps both call sites source-compatible — no test or caller of the original
  functions needed to change when `--explain` was added.
- **Why is `reasoning` merged (read-modify-write) instead of each node returning its own key?**
  LangGraph's partial-state merge (see `06-langgraph-state.md`) is per-key: if `classify` returned
  `{"reasoning": {"classify": "..."}}` and `score` later returned `{"reasoning": {"score": "..."}}`,
  the second write would *replace* the whole `reasoning` dict, losing `classify`'s entry. Reading the
  existing dict off state before returning the merged copy is the standard LangGraph idiom for
  accumulating into a dict-valued field across multiple nodes.

## 4. Verify it yourself

```bash
uv run python learn/09_explainability.py
```

**Expected:** No network call. The script imports the *real* `full_confidence_breakdown` and
`sla_risk_breakdown` from `app.analyze.scoring` (the exact functions `score` calls in production)
and runs them on a worked example, printing each weighted term and verifying by assertion that they
sum to the reported `final` value — proving the "decomposed score" claim rather than just describing
it.

## 5. Self-quiz

1. A ticket has `confidence_breakdown = {"agreement": 1.0, "sigmoid_top_score": 0.6, "consistency":
   0.0, "penalty": 0.15, ...}`. Without re-running the code, compute `final` using the weights
   `W_AGREEMENT=0.5`, `W_SCORE=0.3`, `W_CONSISTENCY=0.2`. What does the `0.0` for `consistency` tell
   you about the classify node's output on that call?
2. Why does `?explain=true` never make an additional LLM or LangSmith call, even though it returns
   per-node "rationale" strings?
3. If you deleted the `reasoning` accumulator and only kept `confidence_breakdown`/`sla_breakdown`,
   what would `debug["nodes"]` look like, and what capability would you lose?

<details><summary>Answers</summary>

1. `final = clamp01(0.5*1.0 + 0.3*0.6 + 0.0 - 0.15) = clamp01(0.5 + 0.18 + 0.0 - 0.15) = 0.53`.
   `consistency = 0.0` means either the LLM `classify` node's queue didn't match the retrieval
   `majority_vote` queue, or one of them was `None` — the two label sources disagreed (or one is
   missing), so the +0.2 consistency bonus wasn't awarded.
2. `_build_debug` is a pure, synchronous mapping over the *already-computed* final `TicketState` —
   `reasoning`, `confidence_breakdown`, `sla_breakdown`, and `neighbors` were all populated while the
   graph ran (regardless of the `explain` flag). `explain=true` only controls whether that already-
   materialized data is copied into the response; it doesn't trigger any new work.
3. `debug["nodes"]` would be an empty list (`reasoning` defaults to `{}` when absent), so you'd still
   see the final confidence/SLA numbers but lose the per-node "why" narrative — e.g. you couldn't
   tell whether `classify` fell back to `majority_vote` because the LLM call failed, or whether
   `clarify` used the LLM-generated questions vs. the missing-info fallback questions.

</details>

## 6. Takeaway

"Explainability is a self-contained, in-app accumulator (`reasoning` + confidence/SLA breakdowns)
built from the same deterministic functions the graph already runs — so `?explain=true` shows the
exact arithmetic behind a decision without depending on LangSmith or making any extra calls."
