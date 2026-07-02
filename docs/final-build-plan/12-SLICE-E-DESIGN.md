# 12 — Slice E Design: Deploy & Harden

Design pass for Milestone **M-E** (the final slice). Build order maps to the E1–E11 outline on epic
`BEA-141` / GitHub #14. Decisions: `05-DECISIONS-LOCKED.md → D16`. Reaffirms D10 (Docker → Render).

## Purpose
Turn QueuePilot from "runs on my machine" into a **live, hardened, shareable demo** — the payoff for
the portfolio. Two phases, deliberately ordered:

1. **Containerize locally first (learn by doing).** Build + run the app in Docker on the dev machine,
   with a guided walkthrough of containerization concepts, *before* any cloud step. This is a graded
   📚 learning goal, not just a deploy chore.
2. **Harden + deploy.** Invite-code auth, rate limiting + a daily quota cap, CI, then deploy the same
   image to Render behind a public URL.

Closes the roadmap's last gap: a clickable demo a recruiter can open.

## Decisions (recommended — confirm; locked as D16)
| Topic | Choice | Why |
|---|---|---|
| **Deploy target** | **Docker → Render (free tier)** (reaffirms D10) | One container serves UI+API; free tier fits a stateless app (all state is external SaaS). Cold start ~30–60s after 15-min idle is acceptable; $7/mo Starter is the always-on option during active job-hunting. |
| **Auth** | **Single shared invite code → signed HTTP-only cookie** | Gates the public demo without user management (out of scope per `00`). Same-origin cookie, which D13 was designed around. |
| **Rate limiting** | **In-process per-IP** (returns the `429` reserved in `03`) | No infra; fine for one free instance. Redis deferred (only needed for horizontal scale). |
| **Quota guard** | **Invite + rate limit + global daily cap** | A leaked code can't drain the free Voyage/Groq/Gemini/Pinecone/LangSmith tiers overnight. |
| **CI** | **GitHub Actions: ruff + mypy + offline pytest + frontend build/vitest** | Secret-free, fast, keeps `main` green. Nightly eval (LangSmith Service key) deferred. |

## Phase 1 — Containerize locally (E1–E3) 📚

**Multi-stage `Dockerfile`** (the app needs the React `dist` built, then a Python runtime to serve it):

```
# Stage 1 — build the frontend (Node) → /frontend/dist
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build            # tsc -b && vite build → dist/

# Stage 2 — Python runtime (uv), copy app + built dist, run uvicorn
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app/ ./app/
COPY data/artifacts/ ./data/artifacts/    # BM25 params needed at runtime
COPY --from=frontend /frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
(Exact base tags/flags finalized during the hands-on build.) A **`.dockerignore`** excludes `.venv/`,
`node_modules/`, `.git/`, `data/raw/`, `__pycache__/`, `tests/`, `.env`, so the build context is lean
and no secrets leak into the image.

**Local run (taught step-by-step):**
```
docker build -t queuepilot:local .
docker run --rm -p 8000:8000 --env-file .env queuepilot:local
# → open http://localhost:8000 : console + /analyze work against the real stack
```
Concepts covered live: image vs. container, layers & caching, multi-stage builds, build context &
`.dockerignore`, `--env-file` secret injection (never bake `.env` into an image), port publishing
(`-p host:container`), `EXPOSE` vs. publish, and why we run `--host 0.0.0.0` inside a container.

**Daemon prerequisite:** the dev machine has the Docker CLI (Homebrew) but the daemon isn't running —
first hands-on action is starting Docker Desktop (`open -a Docker`) or installing a runtime (colima).

## Phase 2 — Harden (E4–E7)

**Auth (E4–E5, contract change D16).** `app/auth.py`: `POST /login {code}` → if `code == INVITE_CODE`,
set a **signed HTTP-only, SameSite=Lax cookie** (signed with `SESSION_SECRET` via `itsdangerous`).
A FastAPI dependency gates `POST /analyze` and `POST /feedback` → `401` without a valid cookie. The
console shows a small **gate screen** (code entry) when unauthenticated; `GET /health` stays open (for
Render health checks). New env: `INVITE_CODE`, `SESSION_SECRET`.

**Rate limiting + daily cap (E6).** Per-IP limit (e.g. `slowapi`) on `/analyze` + `/feedback` → `429`
with a friendly body. A process-global **daily request counter** (resets at UTC midnight) → `429`/`503`
with "demo quota reached, try tomorrow" when exceeded. New env: `RATE_LIMIT_PER_MIN`, `DAILY_CAP`.

**📚 learning artifacts:**
- `13-containerization` — images/layers/multi-stage/`.dockerignore`/env injection (Phase 1). Runnable
  proof follows the infra-note precedent (A5/A7): the `docker build` + `docker run` walkthrough +
  a tiny inspect script (image size, layers) rather than a pure-Python demo.
- `14-securing-a-public-api` — invite-cookie auth, per-IP rate limiting, daily caps, 12-factor secrets.
  Runnable: a script exercising the signed-cookie sign/verify + the rate-limit counter offline.

## Phase 3 — CI + Deploy (E8–E9)

**CI (E8).** `.github/workflows/ci.yml`: `uv sync` → `ruff check` → `mypy` → `pytest` (offline; the
integration tests stay gated behind `QUEUEPILOT_RUN_INTEGRATION`), plus `frontend`: `pnpm install` →
`pnpm build` → `pnpm test`. No secrets required.

**Deploy (E9).** `render.yaml` (Blueprint): a Docker web service, `healthCheckPath: /health`, env vars
declared (values set in the Render dashboard — provider keys, `INVITE_CODE`, `SESSION_SECRET`). Render
auto-deploys on push to `main`. **Needs the user:** connect the Render account + paste secrets; then a
live-URL smoke test (login → analyze → feedback). This is the one step I cannot do autonomously.

## Config additions (`app/config.py`)
`invite_code`, `session_secret`, `rate_limit_per_min` (default e.g. 20), `daily_cap` (default e.g. 500),
plus a `PORT` the container respects. `.env.example` updated; all secrets stay server-side.

## Build order
| ID | Task | 📚 | Deps |
|---|---|---|---|
| **E1** | `.dockerignore` + multi-stage `Dockerfile` (Node build → Python/uv runtime); build locally | | — |
| **E2** | Run the container locally against real `.env`; verify `/health` + console + `/analyze`; guided concept walkthrough | | E1 |
| **E3** | 📚 `13-containerization` doc + runnable proof + LEARNING-LOG row | 📚 | E2 |
| **E4** | Invite-code auth: `app/auth.py`, `POST /login`, signed cookie, gate dependency on `/analyze`+`/feedback` (D16) | | — |
| **E5** | Console gate screen (code entry) + authed state; `GET /health` stays open | | E4 |
| **E6** | Rate limiting (per-IP → 429) + global daily cap; config + `.env.example` | | — |
| **E7** | 📚 `14-securing-a-public-api` doc + runnable script + LEARNING-LOG row | 📚 | E4,E6 |
| **E8** | GitHub Actions CI: ruff + mypy + offline pytest + frontend build/vitest | | — |
| **E9** | `render.yaml` + Render deploy (user connects account/secrets) + live-URL smoke test | | E1,E4,E6 |
| **E10** | Tests: auth (cookie sign/verify, gating, 401), rate-limit 429, daily cap; contract tests | | E4,E6 |
| **E11** | Docs: README deploy + demo-URL + attribution; update `04-BUILD-SEQUENCE`, `06-ARCHITECTURE` | | all |

### Slice E exit criteria
- `docker build` + `docker run` work locally; the containerized app serves the console + `/analyze`
  against the real stack. 📚 `13-containerization` complete.
- Public demo on Render behind an invite code; `/analyze`+`/feedback` gated, rate-limited, daily-capped;
  `/health` open. Live-URL smoke test (login → analyze → feedback) passes.
- CI green on PRs (ruff/mypy/offline pytest + frontend build). Both 📚 artifacts logged.
- `main` clean via squash-merged PR; README has a clickable demo link.

## Constraints
- **Local-first**: no cloud step until the container builds and runs locally and the 📚 concept lands.
- **No secrets in the image**: `.env` is injected at run (`--env-file` locally, Render env vars in prod);
  `.dockerignore` keeps `.env` and `data/raw/` out of the build context.
- **Same `/analyze` contract**: auth/rate-limit are additive (401/429); the response envelope is unchanged.
- **Graceful health**: `GET /health` is unauthenticated + unthrottled so Render's health check passes.
- **Free-tier posture**: one stateless instance; cold starts accepted; daily cap protects provider quotas.
