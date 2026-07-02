# 05 — Decisions Locked 🔒

ADR-style log of decisions already made. **Do not relitigate without explicit user sign-off.**
If a decision changes, append a new entry (don't edit history) and update the affected locked doc.

All decisions below: **2026-06-29**, during the initial brainstorm.

---

### D1 — Lean job-fit posture
**Choice:** build the clean FastAPI+LangGraph+Pinecone+LangSmith core; **defer** Azure Service Bus,
GraphQL, and OpenAI-only wiring.
**Considered:** max box-coverage (wire Azure + GraphQL + OpenAI); core+Azure-only.
**Why:** cheapest/cleanest path to a focused v1; Azure and GraphQL are deferred as out-of-scope
for now — accepted trade-off.

### D2 — Pinecone single sparse-dense index for hybrid
**Choice:** one index holding dense+sparse; supply our own vectors.
**Considered:** Pinecone integrated sparse model; dense-only now.
**Why:** current Pinecone-recommended approach (verified against live docs); genuine hybrid checks
the "hybrid retrieval" gap. Requires query-time score normalization.

### D3 — Dense = Gemini, Sparse = BM25 (`pinecone-text`) *(superseded by D11 for the default provider)*
**Choice:** Gemini dense embeddings + locally-generated BM25 sparse.
**Why:** low cost; Gemini gives only dense, so BM25 supplies the sparse half. Dimension is fixed at
first index creation (see `02`).
*Note: D11 switches the default dense provider to Voyage `voyage-3.5-lite` (1024 dims). Gemini
remains a registry drop-in via `EMBEDDING_PROVIDER=gemini`.*

### D4 — Swappable LLM provider registry (OpenAI a drop-in)
**Choice:** small provider abstraction defaulting to a cheap/fast model; OpenAI selectable.
**Considered:** OpenAI-only; Gemini-only.
**Why:** near-zero cost, demonstrates provider abstraction, AND lets us show OpenAI working as a
selectable drop-in. Not used in Slice A's baseline.

### D5 — Learning layer is a core graded requirement
**Choice:** every slice ships all four forms — annotated concept docs, runnable concept scripts,
checkpoints/self-quiz, and an opt-out in-app `--explain` debug mode (lands in Slice C).
**Why:** the project is also a learning vehicle; skipping teaching artifacts
defeats a primary goal.

### D6 — Spec Slice A fully; roadmap B–E
**Choice:** full buildable spec for Slice A now; B–E as lightweight epics expanded when started.
**Why:** prove the retrieval loop before over-designing later phases whose shape depends on A.

### D7 — Slice A baseline uses pure retrieval majority-vote (no LLM)
**Choice:** derive category/queue/priority from neighbor labels; confidence v0 = blend(top score,
label agreement).
**Why:** isolates "does retrieval work?" before the LLM enters in Slice B; cheapest and explainable.

### D8 — Corpus: ~3k English-only tickets (configurable cap)
**Choice:** `CORPUS_CAP` default 3000, English filter.
**Why:** cheap embed cost, inside Pinecone free tier, enough for useful retrieval; raise later.

### D9 — Two-repo strategy
**Choice:** `queuepilot` flagship (private until end of Slice A, then public; clean `main`,
branch+PR per slice) + `queuepilot-lab` (private permanent sandbox for experiments).
**Why:** recruiters should land on a working demo, not a half-scaffold; experiments stay out of the
flagship's history.

### D10 — Deploy target: Docker → Render
**Choice:** Dockerized FastAPI on Render, same app serves UI + API.
**Why:** simplest demo-link path; deployment is part of the portfolio story.

### D11 — Embeddings provider: Voyage `voyage-3.5-lite` (1024 dims) behind a swappable registry (**supersedes D3**)
**Date:** 2026-06-30.
**Choice:** Default embedding provider is Voyage `voyage-3.5-lite` at 1024 dims, selected via
`EMBEDDING_PROVIDER=voyage`. Provider is resolved at runtime through a registry
(`_PROVIDERS` dict in `app/providers/embeddings.py`); Gemini `gemini-embedding-001` (768 dims)
remains a verified drop-in (`EMBEDDING_PROVIDER=gemini`).
**Why:** Voyage gives **200 M free tokens** per month — our ~0.35 M-token corpus ingests at $0
with no rate-limit grind. The registry design keeps OpenAI / Gemini as provable drop-ins, which
keeps OpenAI a provable drop-in without wiring it as the default. `EMBED_DIM` resolves
to the active provider's dimension at import time so `pinecone_store.ensure_index` always asserts
the right index width.

### D12 — Chat LLM for Slice B: Groq `llama-3.3-70b-versatile` behind a registry
**Date:** 2026-06-30.
**Choice:** Default chat (generative) model is Groq `llama-3.3-70b-versatile`, selected via
`CHAT_PROVIDER=groq`, behind a `ChatModel` registry (mirrors the embedding registry, D4). Gemini and
OpenAI (`gpt-oss-20b`, gpt-4o-mini) remain drop-ins.
**Considered:** Gemini Flash-Lite (reuse key), OpenAI gpt-4o-mini (job-box).
**Why:** free + fastest inference (Groq LPU) for a demo; strong at the classification + short
generation the workflow needs; registry keeps the others provable drop-ins. Embeddings stay on Voyage.

---

All decisions below: **2026-07-01**.

### D13 — Frontend: Vite/React/Tailwind/shadcn console served by FastAPI (refines 01)
**Date:** 2026-07-01.
**Choice:** the Slice C console is a Vite + React + TypeScript + Tailwind + shadcn/ui SPA, built to
static assets and served by the **same FastAPI app** (`01-TECH-STACK-LOCKED.md`'s "App shell" row).
**Considered:** vanilla HTML/JS dashboard (matches "minimal dashboard" wording in `01` literally, but
too thin for a portfolio-grade UI); a separate Next.js app on Vercel (nicer DX, but splits the
deploy into two origins/hosts).
**Why:** a real component-driven UI closes the "no working frontend" gap for a portfolio project
without abandoning D10 — the built static assets still ship inside the one Dockerized FastAPI
container, so there's still exactly one deploy target. Keeping it same-origin also avoids
cross-origin cookie complications when Slice E's signed HTTP-only cookie auth lands. This refines,
not contradicts, `01`'s "App shell" row — "minimal dashboard" becomes "Vite/React/shadcn console,
same app serves UI + API." **Build is paused pending a dedicated UI-design session; the direction is
locked now so backend work (tracing, `--explain`) isn't blocked.**

### D14 — `debug` response field for `--explain` (extends 03)
**Date:** 2026-07-01.
**Choice:** add a new reserved, optional field to `AnalyzeResponse`: `debug: dict | None = None`,
populated only when the request is made with `?explain=true`; `None` otherwise. The existing `trace`
field is unchanged — it stays exactly as `03-API-CONTRACT.md` already specified (a LangSmith run
summary), populated on every call once Slice C's tracing wiring lands, independent of `--explain`.
**Considered:** folding explain output into `trace` (rejected — conflates "is this run traced in
LangSmith" with "give me the in-app reasoning trail," which have different audiences, different
data sources, and different availability, e.g. `debug` must work with zero LangSmith key).
**Why:** consistent with `03`'s reserved-field, forward-compatible envelope design (D-philosophy of
additive-only fields) — old callers see `debug: null` and are unaffected; `--explain` consumers get a
self-contained, offline-testable reasoning trail without depending on LangSmith being configured.

---

All decisions below: **2026-07-02**.

### D15 — Slice D evaluation: new `POST /feedback` endpoint + eval design (extends 03)
**Date:** 2026-07-02.
**Choice:** Slice D adds an evaluation layer with these locked decisions:
1. **New endpoint `POST /feedback`** (extends the 🔒 `03-API-CONTRACT.md` — additive, does not touch
   `/analyze`): body `{run_id, score, correction?, comment?}` → `langsmith.create_feedback` on the
   referenced run (join key = `trace.run_id` from Slice C), and appends corrections to a
   `queuepilot-feedback` dataset (the flywheel). Returns `200 {"ok": true}`; graceful `200` no-op +
   log when LangSmith is unconfigured; `422` on bad body.
2. **LLM-as-judge = Gemini** (different-model judge), not Groq — Groq `llama-3.3-70b` generates the
   suggested replies, so grading with the same model is self-preference bias. Gemini key already
   configured; still free.
3. **Eval dataset = post-cap held-out split** — sampled from English rows **beyond** `CORPUS_CAP`
   (indices `[3000:]`, provably not in the Pinecone index → zero retrieval leakage), stratified by
   queue×priority, plus hand-authored edge cases. A leakage assertion enforces the guarantee.
4. **Feedback surface = `POST /feedback` API + a console `FeedbackWidget`** in the existing built-out
   `frontend/` console.
5. **CI deferred** — the eval runner is local/manual (Personal token); the CI seam (LangSmith Service
   key, nightly Action) is documented for Slice E, not wired in Slice D.
6. **`FeedbackRequest.text` (additive, post-hoc)** — `text` is an OPTIONAL additive field on
   `FeedbackRequest` (does not change the `POST /feedback` request shape's required fields). When a
   caller supplies the original ticket text alongside a `correction`, it is attached to the
   `queuepilot-feedback` flywheel example's `inputs` (`{"text": ..., "run_id": ...}`) instead of just
   `{"run_id": ...}`, so `eval.dataset`'s `analyze_target` (which reads `inputs["text"]`) can actually
   replay flywheel corrections as usable eval data. Omitting `text` preserves the original
   `run_id`-only behavior.
**Considered:** feedback folded into `/analyze` (rejected — different verb, audience, and lifecycle);
reusing Groq as judge (rejected — self-preference bias); seeded random split (rejected — forces a
re-index for no gain over the post-cap pool); wiring CI now (rejected — pulls Slice-E ops forward).
**Why:** closes the "LangSmith eval/experiments" job gap with an additive, offline-testable eval layer
that keeps `/analyze` untouched and validates the A/B confidence blend via a calibration evaluator.
Full design: `11-SLICE-D-DESIGN.md`.

### D16 — Slice E deploy & harden: Docker→Render, invite-cookie auth, rate limiting (extends 03)
**Date:** 2026-07-02.
**Choice:** Slice E ships the deploy/hardening layer with these locked decisions:
1. **Containerize local-first, then Render (reaffirms D10).** One multi-stage image (Node builds the
   React `dist` → lean Python/uv runtime serves UI+API) built and run **locally first** as a graded
   📚 learning goal, then deployed to **Render's free tier** (cold starts ~30–60s after 15-min idle
   accepted; $7/mo Starter is the optional always-on mode). Same image local and cloud.
2. **Auth = single shared invite code → signed HTTP-only cookie** (extends the 🔒 `03` contract,
   additive): new `POST /login {code}` → sets a `SameSite=Lax`, HTTP-only cookie **signed with
   stdlib HMAC** (`SESSION_SECRET`) — no new dependency. A FastAPI dependency gates `POST /analyze`
   and `POST /feedback` (`401` without a valid cookie); `GET /health` stays open for Render health
   checks. New env: `INVITE_CODE`, `SESSION_SECRET`.
3. **Rate limiting = in-process per-IP** (`429`, the code `03` reserved) **+ a global daily cap**
   (`429`/`503` when exceeded). Both in-process (no Redis, no new dep) — fine for one free instance;
   Redis deferred to horizontal scale. New env: `RATE_LIMIT_PER_MIN`, `DAILY_CAP`.
4. **CI = GitHub Actions**: `ruff` + `mypy` + offline `pytest` + frontend `pnpm build`/`vitest` on PRs;
   secret-free. Nightly eval (LangSmith Service key) still deferred.
5. **No new runtime deps** for auth/rate-limit (stdlib `hmac` signing + in-process counters) to keep
   the image lean and the supply chain small.
**Considered:** Redis-backed rate limiting (rejected — overkill for one free instance); named/per-user
codes or full accounts (rejected — out of scope per `00`); a separate host for the SPA (rejected —
D13 keeps it same-origin, one container).
**Why:** makes QueuePilot a live, invite-gated, quota-protected public demo behind a single Dockerized
Render service, while teaching containerization hands-on. Full design: `12-SLICE-E-DESIGN.md`.
