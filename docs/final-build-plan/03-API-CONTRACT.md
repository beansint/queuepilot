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

## GraphQL — `/graphql` (Slice F — D17)

**Additive** transport over the *same* services as REST — not a replacement. Built with Strawberry
(`strawberry-graphql[fastapi]`), co-mounted on the FastAPI app. Resolvers call
`get_graph_analyzer().analyze()` and `submit_feedback()`, so GraphQL results are **at parity** with
REST for the same input.

### Schema (SDL)
```graphql
type Query {
  analyze(text: String!, explain: Boolean = false): Analysis!
  health: Health!
}
type Mutation {
  submitFeedback(input: FeedbackInput!): Boolean!    # thumbs + optional correction; best-effort
}

type Analysis {                    # 1:1 with AnalyzeResponse (camelCased)
  category: String
  queue: String
  priority: String
  confidence: Float!
  similarTickets: [SimilarTicket!]!
  sentiment: Sentiment             # typed {frustration, negativity}
  slaRisk: Float
  escalate: Boolean
  clarification: [String!]
  suggestedReply: String
  trace: JSON                      # loose LangSmith summary
  debug: JSON                      # null unless explain: true
}
type SimilarTicket { score: Float!  queue: String  priority: String  type: String  snippet: String! }
type Sentiment { frustration: Float!  negativity: Float! }
type Health { status: String!  app: String!  environment: String! }
input FeedbackInput { runId: String!  score: Int!  correction: JSON  comment: String  text: String }
scalar JSON
```

### Gating & rate limiting
`POST /graphql` reuses the **same** dependencies as REST `/analyze`:
`GraphQLRouter(dependencies=[Depends(require_auth), Depends(rate_limit)])`. So GraphQL is invite-gated
(`401` without a valid `qp_session` cookie when auth is configured; open when unconfigured — same
graceful-degradation as REST) and subject to the per-IP limit + daily cap (`429`). GraphiQL (the
in-browser explorer at `GET /graphql`) therefore requires login first. REST `GET /health` stays open.

### What stays REST (not exposed in GraphQL)
`POST /login`, `POST /logout`, `GET /auth/status` — cookie-setting / session bootstrap belongs on the
transport, not in a resolver (avoids duplicated auth + a wider CSRF surface).

### Invariants
- **Parity:** for the same input, GraphQL `analyze` returns the same values as REST `POST /analyze`;
  the schema is derived from the same `AnalyzeResponse` envelope. Reserved-field ownership by slice
  (see table above) is unchanged.
- Field selection changes only the **response shape over the wire**, never the server-side computation
  (`analyze` runs the full LangGraph regardless of selected fields).
- No server-only data (keys, raw provider responses) appears in any GraphQL field.

### Errors (GraphQL)
- Validation / bad query → a GraphQL `errors` array (HTTP `200`), not `422`/`500`.
- `401` / `429` — auth / rate-limit, raised by the shared dependencies before resolution.
