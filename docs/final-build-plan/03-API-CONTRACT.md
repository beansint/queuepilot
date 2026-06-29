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
```

### Field ownership by slice
| Field | Populated in |
|---|---|
| category, queue, priority, confidence, similar_tickets | **A** |
| sentiment, sla_risk, escalate, clarification, suggested_reply | **B** |
| trace | **C** |

### Errors
- `422` — validation failure (missing `text`, or `len(text) > MAX_INPUT_CHARS`).
- `429` — rate limit exceeded (Slice E).
- `500` — unexpected; body `{"detail": "..."}` with no secret leakage.

### Invariants
- `confidence ∈ [0, 1]`.
- `similar_tickets` ordered by descending `score`.
- Reserved fields are omitted/`null` until their slice lands — **never** repurposed.
- No server-only data (keys, raw provider responses) ever appears in the response.
