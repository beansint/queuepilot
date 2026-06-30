# 08 — Slice B Design: Agentic Workflow (LangGraph)

Approved design pass for Milestone **M-B**. Build order maps to the B1–B11 outline on epic #11.

## Purpose
Replace the Slice A `Analyzer` (pure retrieval + majority vote) with a **LangGraph state machine**
behind the *same* `/analyze` contract — turning the retrieval baseline into a guarded support copilot
that classifies, scores sentiment/SLA/confidence, and decides answer / clarify / escalate.

## Chat model
**Groq `llama-3.3-70b-versatile`** (free, fast) — the default behind a **ChatModel provider registry**
(`CHAT_PROVIDER`, mirrors the embedding registry, D4). Gemini / OpenAI (`gpt-oss-20b` etc.) are
one-config-var drop-ins. **(Decision D12.)**

## State (`TicketState`, a TypedDict threaded through the graph)
```
text: str                       # input ticket (validated)
neighbors: list[Neighbor]       # from retrieve
category / queue / priority: str | None
sentiment: dict | None          # {frustration: float, negativity: float}
missing_info: list[str]         # from assess
sla_risk: float | None
confidence: float
decision: str                   # "answer" | "clarify" | "escalate"
clarification: list[str]
suggested_reply: str | None
escalate: bool
```

## Graph (sequential for v1 — parallelize later if latency matters)
```
START → retrieve → classify → sentiment → assess_missing → score → decide ◇
                                                                     ├ answer   → draft_reply → END
                                                                     ├ clarify  → clarify     → END
                                                                     └ escalate → END
```
- **retrieve** — reuse Slice A hybrid retrieval (no LLM).
- **classify / sentiment / assess_missing / draft_reply / clarify** — LLM nodes (chat registry).
- **score** — deterministic: full blended confidence (extends `confidence_v0` with classification
  certainty + route/priority consistency + missing-info & escalation-risk penalties) + SLA risk.
- **decide** — conditional router: high confidence & no missing info → answer; missing key info →
  clarify; low confidence or high SLA risk → escalate. (Guarded copilot: never overcommit — D-philosophy.)

## Envelope mapping (same `03-API-CONTRACT.md`, reserved fields now filled)
`category/queue/priority` ← classify · `confidence` ← score · `sentiment` ← sentiment ·
`sla_risk` ← score · `escalate` + `clarification` ← decide/clarify · `suggested_reply` ← draft_reply ·
`similar_tickets` ← retrieve. `trace` stays null until Slice C (LangSmith). **No API break.**

## Build order
- **B1** scaffold: `+langgraph`, `TicketState`, `app/analyze/graph.py` (skeleton + `retrieve` node), compile. 📚 LangGraph state.
- **B2** ChatModel registry: `ChatModel` protocol + `GroqChat` (default) behind `get_chat_model()`; Gemini/OpenAI drop-ins.
- **B3** classify · **B5** assess_missing · **B6** sentiment · **B7** score (full confidence + SLA risk).
- **B8** decide router + conditional edges. 📚 guarded-copilot pattern.
- **B9** draft_reply + clarify nodes.
- **B10** swap `Analyzer` → `GraphAnalyzer` behind `/analyze`; populate reserved envelope fields.
- **B11** tests (mocked chat model + gated live) + learning artifacts.

## Constraints
- Same `/analyze` HTTP contract; the endpoint keeps calling one `analyze(text)` entrypoint.
- LLM nodes must degrade gracefully (a node failure shouldn't 500 the whole request — fall back to
  Slice A behavior where possible).
- Offline-testable: chat model injected/mocked; one gated live integration test.
