# 06 — LangGraph state machines

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `B1` · Runnable companion: `uv run python learn/06_langgraph_state.py`

## 1. Concept
**LangGraph** models an LLM workflow as a **state graph**: a typed **state** object flows through
**nodes** (functions) connected by **edges**. The key idea is the **merge**: each node receives the
current state and returns a *partial* dict; LangGraph merges that partial back into the state and
passes it to the next node. You don't mutate a shared object — you return "what changed."

- **State** — a `TypedDict` (here `TicketState`). `total=False` means nodes fill fields incrementally.
- **Node** — `def node(state) -> dict`: reads what it needs, returns only the keys it sets.
- **Edge** — `add_edge(A, B)` runs B after A. `START`/`END` are the entry/exit.
- **Conditional edge** — `add_conditional_edges(node, router_fn, {label: target})` branches on a value
  the router returns (this is how B8's answer/clarify/escalate routing works).

## 2. In QueuePilot
`app/analyze/graph.py` defines `TicketState` and `build_graph(...)`. The B1 scaffold has one real
node, `retrieve` (reusing Slice A hybrid retrieval), wired `START → retrieve → END`. B3–B9 add
`classify → sentiment → assess_missing → score → decide → draft/clarify` onto the same seam. The
compiled graph eventually replaces the hand-composed Slice A `Analyzer` — *behind the same `/analyze`
contract* (`08-SLICE-B-DESIGN.md`).

## 3. Why this way
- **Inspectable control flow** — the routing (answer/clarify/escalate) is explicit graph structure,
  not buried in `if` statements; you can visualize and trace it (Slice C adds LangSmith tracing).
- **Composable & testable** — dependencies are injected into `build_graph`, so the whole graph runs
  on fakes with no network (see `tests/test_graph.py`).
- **Partial-state merge** keeps nodes decoupled: each owns only the fields it produces.

## 4. Verify it yourself
```bash
uv run python learn/06_langgraph_state.py
```
**Expected:** a tiny 2-node graph runs and prints the state *after each node*, showing how each
node's returned partial dict is merged into the running state.

## 5. Self-quiz
1. A node returns `{"queue": "IT"}` — what happens to the other state fields it didn't return?
2. What's the difference between `add_edge` and `add_conditional_edges`, and which one implements
   "answer vs clarify vs escalate"?
3. Why inject `embedder`/`store` into `build_graph` instead of importing them inside the node?

<details><summary>Answers</summary>

1. They're untouched — LangGraph merges the returned partial dict into the existing state; unreturned
   keys keep their current values.
2. `add_edge(A, B)` is an unconditional "then B"; `add_conditional_edges(node, router, {...})` calls a
   router function and jumps to the target keyed by its return value — that's the answer/clarify/escalate branch.
3. Injection makes the graph testable with fakes (no network) and swappable (Voyage/Groq via the
   registries) without editing node code.

</details>

## 6. Takeaway
"A LangGraph node returns *what changed*, not the whole state — the framework merges partials and
moves along edges, so control flow (including escalate-vs-answer) is explicit, inspectable structure."
