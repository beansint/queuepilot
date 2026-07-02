# 03 — API Contract (BINDING 🔒)

Code conforms to this contract, not the reverse. The envelope is designed once and is
**forward-compatible**: later slices populate reserved fields without changing the shape.

## `GET /health`
→ `200 {"status": "ok"}`. No auth (until Slice E).

## `POST /analyze`

### Request
```python
class AnalyzeRequest(BaseModel):
    text: str                         # required; rejected if len > MAX_INPUT_CHARS (422)
    metadata: dict | None = None      # optional passthrough (channel, locale, etc.)
```

### Query params
- `explain` (`bool`, default `false`) — **C**. `POST /analyze?explain=true` opt-in debug mode;
  populates the response `debug` field from an in-app `TicketState` accumulator. Off by default;
  absent or `false` behaves exactly as before (`debug` stays `null`).

### Response — `AnalyzeResponse`
```python
class SimilarTicket(BaseModel):
    score: float
    queue: str | None
    priority: str | None
    type: str | None
    snippet: str

class AnalyzeResponse(BaseModel):
    # --- Slice A populates these ---
    category: str | None
    queue: str | None
    priority: str | None
    confidence: float                 # blended; v0 = retrieval-only
    similar_tickets: list[SimilarTicket]

    # --- reserved; None until the owning slice ---
    sentiment: dict | None = None         # B: {frustration: float, negativity: float}
    sla_risk: float | None = None         # B
    escalate: bool | None = None          # B
    clarification: list[str] | None = None # B
    suggested_reply: str | None = None    # B
    trace: dict | None = None             # C: LangSmith run summary
    debug: dict | None = None             # C: --explain payload (null unless ?explain=true)
```

`trace` is a LangSmith run summary populated on **every** call once Slice C's tracing lands
(`{enabled, run_id, url, latency_ms, project}`, D-tracing design in `09-SLICE-C-DESIGN.md`) —
`enabled: false` with the rest `None` when no LangSmith key is configured. `debug` (D14) is a
separate, in-app reasoning trail populated only when the request is made with `?explain=true`;
it does not depend on LangSmith being configured.

### Field ownership by slice
| Field | Populated in |
|---|---|
| category, queue, priority, confidence, similar_tickets | **A** |
| sentiment, sla_risk, escalate, clarification, suggested_reply | **B** |
| trace, debug | **C** |

### Errors
- `422` — validation failure (missing `text`, or `len(text) > MAX_INPUT_CHARS`).
- `429` — rate limit exceeded (Slice E).
- `500` — unexpected; body `{"detail": "..."}` with no secret leakage.

### Invariants
- `confidence ∈ [0, 1]`.
- `similar_tickets` ordered by descending `score`.
- Reserved fields are omitted/`null` until their slice lands — **never** repurposed.
- No server-only data (keys, raw provider responses) ever appears in the response.

## `POST /feedback` (Slice D — D15)

Additive endpoint for the human-feedback flywheel. Does **not** touch `/analyze`. The join key is
`trace.run_id` returned by a prior `POST /analyze` (Slice C).

### Request
```python
class FeedbackRequest(BaseModel):
    run_id: str                       # LangSmith run id from a prior analyze trace
    score: int                        # thumbs: 1 (up) or 0 (down)
    correction: dict | None = None    # optional human fix, e.g. {"queue": "...", "priority": "..."}
    comment: str | None = None
    text: str | None = None           # optional original ticket text (additive; flywheel usability)
```

### Response
→ `200 {"ok": true}`. Calls `langsmith.create_feedback(run_id, key="user_thumbs", score, comment,
trace_id=run_id)`; when `correction` is present, also appends a corrected example to the
`queuepilot-feedback` dataset — with `inputs={"text": text, "run_id": run_id}` when `text` was
supplied, else `inputs={"run_id": run_id}` (best-effort). **Graceful no-op** (still `200`, logged)
when LangSmith is unconfigured — feedback is best-effort, never blocks the caller.

### Errors (feedback)
- `422` — validation failure (missing `run_id`, `score` not in {0,1}).
- `500` — unexpected; body `{"detail": "..."}` with no secret leakage.
