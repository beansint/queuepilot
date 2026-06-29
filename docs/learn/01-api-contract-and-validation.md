# 01 — API contract & validation (contract-first Pydantic)

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `A2` · Runnable companion: `uv run python learn/01_schemas_demo.py`

## 1. Concept
**Contract-first design:** define the request/response *shapes* before the logic, and let the
framework enforce them. With Pydantic + FastAPI:
- A model field is typed and validated; bad input raises `ValidationError`, which FastAPI turns into
  an HTTP **422** automatically — you never hand-write that check in the handler.
- A **forward-compatible** response keeps a stable shape over time by adding fields as `Optional`
  with safe defaults, so old clients keep working as new capabilities fill reserved fields.

## 2. In QueuePilot
`app/schemas.py` is the binding contract (mirrors `docs/final-build-plan/03-API-CONTRACT.md`):
- `AnalyzeRequest` — `text` (validated: non-empty, ≤ `MAX_INPUT_CHARS`) + optional `metadata`.
- `AnalyzeResponse` — Slice A fields (`category`, `queue`, `priority`, `confidence`,
  `similar_tickets`) **plus reserved fields** (`sentiment`, `sla_risk`, `escalate`, `clarification`,
  `suggested_reply`, `trace`) that default to `None` until their slice lands.
- `confidence` carries the invariant `0.0 ≤ confidence ≤ 1.0` as a field constraint (`Field(ge, le)`).

## 3. Why this way
- **One envelope from day one** (`05-DECISIONS-LOCKED.md` shape) means Slice B/C add behavior without
  breaking the API — the endpoint signature never changes (`06-ARCHITECTURE.md`: `main.py` keeps
  calling one `analyze(text)`).
- **Validation lives in the model**, not the handler, so it's reusable and unit-testable in isolation
  (no HTTP needed), and the rule (`MAX_INPUT_CHARS`) stays config-driven via `get_settings()`.

## 4. Verify it yourself
```bash
uv run python learn/01_schemas_demo.py
```
**Expected:** a valid request is parsed (and `text` trimmed); an over-limit request raises a
`ValidationError` (the same error FastAPI renders as 422); and a freshly built `AnalyzeResponse`
shows every reserved field as `None` — proving the envelope is forward-compatible.

## 5. Self-quiz
1. Why put the `MAX_INPUT_CHARS` check in the model validator instead of the `/analyze` handler?
2. What makes the response envelope "forward-compatible," and why does that matter for Slices B–C?
3. A `ValidationError` from a request model becomes which HTTP status, and who produces it?

<details><summary>Answers</summary>

1. It's reusable, testable without HTTP, and keeps a single config-driven rule. Handlers stay thin
   and can't forget the check.
2. Reserved fields are `Optional` with `None`/empty defaults, so adding real values later doesn't
   change the shape or break existing clients — Slice B fills sentiment/escalation, C fills trace.
3. **422 Unprocessable Entity**, produced automatically by FastAPI from the Pydantic error.

</details>

## 6. Takeaway
"Define the contract as typed models first — validation and the 422 come for free, and a
reserved-field envelope lets the system grow without breaking callers."
