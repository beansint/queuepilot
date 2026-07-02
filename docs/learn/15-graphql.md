# 15 — REST vs GraphQL: an additive API layer

> **Learning artifact** — every task that introduces a concept ships one of these.
> Pattern: `docs/learn/_TEMPLATE.md` · Log it in `docs/final-build-plan/LEARNING-LOG.md`
> Task: `F7` · Runnable companion: `uv run python learn/15_graphql.py`

## 1. Concept
**REST** exposes *resources* at URLs; the **server** decides the response shape. Want a different
shape? Add a query param, add an endpoint, or over-fetch and throw fields away client-side.

**GraphQL** exposes one endpoint and one typed **schema**; the **client** declares the exact shape it
wants, and the server returns precisely that — no more, no less. The response mirrors the query.
(*GraphQL ≠ LangGraph — unrelated; the shared "graph" is a coincidence. LangGraph is our workflow
engine; GraphQL is an API transport.*)

The mental model in one line: **REST — ask for a resource, get the server's shape. GraphQL — ask for
a shape, get exactly that shape.**

## 2. In QueuePilot
We expose an **additive** `/graphql` alongside REST, built with **Strawberry**
(`app/graphql/schema.py`, `types.py`). It's a *second adapter over the same services* — resolvers call
the exact same entry points as REST:

- `Query.analyze(text, explain)` → `get_graph_analyzer().analyze()` (the same LangGraph the REST
  `POST /analyze` runs), then `Analysis.from_response()` maps the Pydantic `AnalyzeResponse` to the
  GraphQL type — the single parity boundary.
- `Query.health`, `Mutation.submitFeedback` → mirror `GET /health` / `POST /feedback`.
- The large envelope (12 fields, ~half optional) is the payoff case: `sentiment` becomes a typed
  `Sentiment` object, `trace`/`debug` map to the `JSON` scalar, and every field is camelCased
  (`sla_risk` → `slaRisk`).

Gating reuses the REST dependencies verbatim: `GraphQLRouter(dependencies=[require_auth, rate_limit])`
(`app/main.py` mounts it *before* the SPA catch-all). Login/logout stay REST — cookie-setting is
session bootstrap, not data.

## 3. Why this way
Decision: `05-DECISIONS-LOCKED.md → D17` (un-defers GraphQL, supersedes D1). Design:
`13-SLICE-F-DESIGN.md`. We chose **additive + read-focused**, not a REST replacement:

- **Reused services, not a parallel brain** → REST/GraphQL parity is structural; a resolver can't
  drift from `/analyze` because it *is* `/analyze`'s service.
- **Writes (login) stayed REST** → cookie-setting in a GraphQL mutation is *possible* but widens the
  CSRF surface and duplicates auth for no gain.
- **Rejected** the `experimental.pydantic` bridge (hand-written types keep the loose `dict` fields
  clean under mypy --strict) and rewiring the frontend (REST works — GraphiQL surfaces the value
  without regression risk).

## 4. Verify it yourself
```bash
uv run python learn/15_graphql.py
```

**Expected:** the script prints (1) the generated **SDL** — your Pydantic envelope as a typed GraphQL
schema; (2) two queries against the *same* resolver — a 2-field "triage" query returning only
`{queue, confidence}` and a full-envelope query — proving the client controls the shape; (3) a
counter showing the resolver ran **once per query** and the payload sizes (67 vs 402 chars). The
punchline: same server compute, different wire shape. Field selection saves **bytes + client code,
not backend compute** — the graph runs identically regardless of selected fields.

## 5. Self-quiz
1. Two GraphQL clients query `analyze` — one selects `{queue}`, one selects the whole envelope. Does
   the second one make the LangGraph do more work? Why or why not?
2. Why did we keep `POST /login` on REST instead of adding a `login` GraphQL mutation, even though
   Strawberry supports setting cookies in a resolver?
3. `trace` and `debug` map to a `JSON` scalar, but `sentiment` maps to a typed `Sentiment` object.
   What's the reasoning for treating them differently?

<details><summary>Answers</summary>

1. No. The envelope is produced atomically by one `graph.invoke()`; both queries run the identical
   resolver + graph. Field selection only trims what's serialized over the wire, not what's computed.
   (GraphQL saves compute only when a field has its *own* lazy resolver — e.g. `debug` behind the
   `explain` arg.)
2. Login is session *bootstrap* (sets a signed cookie), not data mutation. Keeping it on REST avoids
   duplicating the auth path and widening the CSRF surface we hardened in Slice E. "Possible" ≠
   "appropriate."
3. `sentiment` has a known, fixed shape (`{frustration, negativity}`) worth encoding as a typed,
   introspectable object. `trace`/`debug` are genuinely loose summary dicts — forcing a type on them
   would be brittle, so the `JSON` scalar is the honest representation.

</details>

## 6. Takeaway
GraphQL lets the client declare the response shape against one typed schema, and when it's a second
adapter over the same service, you get client-shaped payloads + an introspectable contract for free —
but not faster backend work; so put GraphQL on the read/analysis surface and keep liveness, cookie-auth,
and best-effort writes on REST.
