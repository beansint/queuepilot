# 13 — Slice F Design: Additive GraphQL API (read + feedback)

Design pass for Milestone **M-F**. Build order maps to the F1–F8 outline on epic GitHub #45 (mirror
Linear). Decisions: `05-DECISIONS-LOCKED.md → D17` (un-defers GraphQL, supersedes D1's deferral).
Extends the 🔒 `03-API-CONTRACT.md`. **Additive** — every REST route and the existing frontend are
untouched.

## Purpose
Expose QueuePilot's read/analysis surface over **GraphQL** alongside the existing REST API, so a
client can request exactly the fields it needs from the large `AnalyzeResponse` envelope (12 fields,
~half optional/expensive) instead of over-fetching or reaching for `?explain=`-style param hacks.

This is both a **portfolio signal** (a typed, introspectable, self-documenting schema + GraphiQL
explorer) and a **graded 📚 learning goal** (REST vs GraphQL, where each fits — the dedicated
concept-15 artifact). It is deliberately scoped: GraphQL for the operations where shape-flexibility
pays; REST stays primary for liveness, cookie-auth, and best-effort writes.

## Why this is cheap + safe here (architecture)
Both transports are thin skins over the **same service functions** — GraphQL is a second adapter,
not a second brain, so REST/GraphQL parity is structural, not maintained by hand:

```
      REST   POST /analyze ────┐
                               ├──► get_graph_analyzer().analyze(text, explain)
   GraphQL   query analyze  ───┘          │  LangGraph: retrieve→classify→…→decide
                                          ▼
                                   AnalyzeResponse (Pydantic)  ← single source of truth
      REST   POST /feedback ───┐
                               ├──► submit_feedback(req) ──► LangSmith
   GraphQL   mutation feedback ┘

   login / logout / auth_status ─────► REST ONLY  (sets the qp_session cookie)
```

## Decisions (locked as D17)
| Topic | Choice | Why |
|---|---|---|
| **Library** | **Strawberry** (`strawberry-graphql[fastapi]`) | Code-first, Pydantic-native, ships a mypy plugin — fits the contract-first + strict-typing stack. `GraphQLRouter` co-mounts on the existing FastAPI app (same origin, same Docker image, same Render deploy). |
| **Surface** | `Query.analyze`, `Query.health`, `Mutation.submitFeedback` | The read/analysis surface + the one clean mutation (feedback writes to the LangSmith dataset, sets no cookie, is best-effort). |
| **Writes** | login/logout/auth-status **stay REST** | Cookie-setting is session bootstrap, not data mutation; keeping it on REST avoids duplicating auth and widening the CSRF surface hardened in Slice E. (Cookie-in-mutation is *possible* per Strawberry docs — but not appropriate.) |
| **Gating** | Reuse `require_auth` + `rate_limit` verbatim as `GraphQLRouter(dependencies=[...])` | Same invite-cookie + per-IP/daily-cap guards as REST `/analyze`; one source of truth, zero duplication. Consequence: GraphiQL requires login first (consistent with an invite-gated demo). REST `/health` stays open for Render's probe. |
| **Frontend** | Data layer **unchanged** (stays on REST); enable **GraphiQL** at `/graphql` + surface it | No regression risk. GraphiQL explorer + a landing link/README section give the portfolio payoff without touching the app's data flow. |
| **Mapping** | Hand-written Strawberry types + explicit `from_response()` mapper (not `experimental.pydantic`) | Full control over the dict→JSON/typed-object split below; keeps mypy-strict clean. |

## The one real friction — loosely-typed `dict` fields
GraphQL is strongly typed; the envelope has loose dicts. Mapping decisions:

| `AnalyzeResponse` field | GraphQL representation |
|---|---|
| `category, queue, priority, confidence, sla_risk, escalate, suggested_reply` | scalars — direct map |
| `similar_tickets` | `[SimilarTicket!]!` (typed object) |
| `sentiment` `{frustration, negativity}` | typed `Sentiment` object (upgrade from loose dict) |
| `clarification` | `[String!]` |
| `trace`, `debug` | `JSON` scalar (`strawberry.scalars.JSON`) — genuinely loose summaries |

GraphQL convention camelCases fields: `similar_tickets → similarTickets`, `sla_risk → slaRisk`,
`suggested_reply → suggestedReply` (the mapper handles it).

## SDL (target)
```graphql
type Query {
  analyze(text: String!, explain: Boolean = false): Analysis!
  health: Health!
}

type Mutation {
  submitFeedback(input: FeedbackInput!): Boolean!
}

type Analysis {
  category: String
  queue: String
  priority: String
  confidence: Float!
  similarTickets: [SimilarTicket!]!
  sentiment: Sentiment
  slaRisk: Float
  escalate: Boolean
  clarification: [String!]
  suggestedReply: String
  trace: JSON
  debug: JSON          # null unless explain: true
}

type SimilarTicket { score: Float!  queue: String  priority: String  type: String  snippet: String! }
type Sentiment { frustration: Float!  negativity: Float! }
type Health { status: String!  app: String!  environment: String! }

input FeedbackInput {
  runId: String!
  score: Int!          # thumbs: 1 (up) or 0 (down)
  correction: JSON
  comment: String
  text: String
}

scalar JSON
```

## What GraphQL does / does NOT buy us (honest scope)
- **Does:** client-shaped payloads (less over-fetching), one introspectable schema (GraphiQL,
  self-documenting), no endpoint sprawl (`/analyze/slim` etc.).
- **Does NOT:** speed up the LLM — `analyze` runs the whole LangGraph regardless of selected fields
  (the envelope is produced atomically by one `graph.invoke()`); field selection saves bandwidth +
  client code, not backend compute. HTTP caching also gets harder (POST is CDN-opaque) — a reason
  `/health` and cookie-auth stay on REST. The classic **N+1** trap doesn't bite us (neighbors come
  back in one Pinecone query), but it's named in the learning doc.

## Files (all new/additive)
```
app/graphql/
  __init__.py
  schema.py     # strawberry.Schema(Query, Mutation) + GraphQLRouter factory
  types.py      # Strawberry types + from_response()/from-state mappers
  context.py    # context_getter (exposes request/response for resolvers)
app/main.py     # include_router(graphql_app, prefix="/graphql") BEFORE _register_frontend_routes(app)
pyproject.toml  # + "strawberry-graphql[fastapi]"; + mypy plugin "strawberry.ext.mypy_plugin"
```
**Mount order:** include the GraphQL router *before* `_register_frontend_routes(app)`. The SPA mount
is `/`-only (not a greedy catch-all — see `app/main.py`), so `/graphql` is safe; ordering is
belt-and-suspenders.

## 📚 learning artifact (graded — D5)
- `docs/learn/15-graphql.md` (from `_TEMPLATE.md`, 6 sections) — REST vs GraphQL, why additive,
  field-selection over a big envelope, mapping Pydantic→SDL, why writes stayed REST, the N+1 trap.
- `learn/15_graphql.py` — standalone: boots the schema in-process, runs a field-selected query
  proving a client can fetch `{queue, confidence}` only vs the full envelope, and prints the
  generated SDL (Pydantic→GraphQL made visible).
- New `LEARNING-LOG.md` **Slice F** row → `done` only when doc + script + self-quiz exist and the
  script runs.

## Build order
| ID | Task | 📚 | Deps |
|---|---|---|---|
| **F1** | ADR `D17` + locked-doc updates (`01`/`00`/`03`) + this design doc + `04-BUILD-SEQUENCE` + README roadmap; milestone **M-F** + issues | | — |
| **F2** | `strawberry-graphql[fastapi]` dep + mypy plugin wiring; `uv lock`; build green | | F1 |
| **F3** | GraphQL types + Pydantic→SDL mappers (dict-field handling: `Sentiment` object, `JSON` scalar) | | F2 |
| **F4** | Schema + resolvers (`Query.analyze`, `Query.health`, `Mutation.submitFeedback`) reusing existing services | | F3 |
| **F5** | Mount at `/graphql` + gating (auth + rate-limit parity) + GraphiQL enabled | | F4 |
| **F6** | Tests: `tests/test_graphql.py` (see matrix) | | F4,F5 |
| **F7** | 📚 `15-graphql` doc + `learn/15_graphql.py` + LEARNING-LOG row | 📚 | F4 |
| **F8** | Surface GraphiQL: landing "Explore the GraphQL API →" link + README GraphQL section | | F5 |

## Test matrix (`tests/test_graphql.py`)
Follows the existing FastAPI `TestClient` + injected-fake-graph pattern (see `test_analyze`):
- `analyze` query returns a populated envelope (fake graph, no network).
- **Field selection:** requesting `{queue confidence}` returns only those fields.
- **Parity:** same input → GraphQL `analyze` == REST `/analyze` values.
- `sentiment` typed-object shape; `trace`/`debug` `JSON`; `debug` null unless `explain: true`.
- **Auth gating:** unauthenticated `/graphql` → 401 when auth configured; open when unconfigured
  (graceful-degradation parity with REST).
- **Rate limit:** 429 after cap (reuses `ratelimit.reset_state()`).
- `submitFeedback` → `true`; best-effort no-op when LangSmith unconfigured.
- Invalid query / oversized text → GraphQL error shape (not a 500).
- `health` query open + correct.

## Slice F exit criteria
- `/graphql` serves `analyze` (query) + `submitFeedback` (mutation), gated + rate-limited like REST;
  GraphiQL loads (post-login). Field selection + REST parity proven by tests + a live smoke check.
- 📚 `15-graphql` complete (doc + runnable script + self-quiz + LEARNING-LOG row).
- Full suite + `ruff` + `mypy --strict` (incl. Strawberry plugin) green; REST/auth/SPA regression clean.
- `main` clean via squash-merged PR; `03`/`01`/`00` reflect the un-deferral; `05 → D17` recorded.

## Constraints
- **Additive only:** no REST route or the existing frontend data layer changes; the response envelope
  is unchanged.
- **Single source of truth:** resolvers call the same `get_graph_analyzer().analyze()` /
  `submit_feedback()` — GraphQL must never duplicate analysis or feedback logic.
- **Gating parity:** GraphQL reuses `require_auth` + `rate_limit`; no second auth path.
- **Graceful health:** REST `GET /health` stays open + unthrottled for Render's probe.
- **No secret leakage:** `trace`/`debug` expose only what REST already exposes; no server-only data.
