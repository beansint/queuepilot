# 13 — Containerization (Docker, multi-stage, the local run)

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: E1–E3 (Slice E) · Runnable companion: `uv run python learn/13_containerization.py`

## 1. Concept
A **container** is your app plus everything it needs to run (interpreter, libraries, files) packaged
so it runs the same on any machine with a container runtime — "it works on my machine" becomes "it
works everywhere." Key vocabulary:

- **Image** — the immutable, built artifact (a stack of read-only **layers**). A recipe's output.
- **Container** — a running instance of an image (add a writable layer + a process).
- **Dockerfile** — the recipe: each instruction (`FROM`, `COPY`, `RUN`, …) produces a layer.
- **Layer caching** — Docker reuses a layer if its instruction + inputs are unchanged. So you copy
  the dependency manifest and install *before* copying the whole source — dependencies (slow) are
  cached until they actually change, and only your fast-changing code re-runs on rebuilds.
- **Multi-stage build** — multiple `FROM` stages; a later stage `COPY --from=`s only the artifacts it
  needs from an earlier one. The heavy build toolchain never ships in the final image.
- **Build context** — everything sent to the daemon at `docker build`; `.dockerignore` trims it
  (and keeps secrets/junk out of the image).

## 2. In QueuePilot
One image serves the React console **and** the FastAPI API (`05-DECISIONS-LOCKED.md` D10/D13). See
the repo root `Dockerfile` + `.dockerignore`:

- **Stage 1 (`node:20-alpine AS frontend`)** — `pnpm install` (manifests copied first for caching) →
  `pnpm build` → `frontend/dist`.
- **Stage 2 (`python:3.12-slim AS runtime`)** — `uv sync --frozen --no-dev` installs deps from
  `uv.lock` (`[tool.uv] package = false` → deps only, no local package build), copies `app/`, the
  runtime `data/artifacts/bm25_params.json`, and `COPY --from=frontend … dist` — then runs
  `uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`.
- **`.dockerignore`** excludes `.venv`, `node_modules`, `data/raw`, and crucially **`.env`** — secrets
  are injected at *run* time, never baked into the image.

Run it locally:
```bash
docker build -t queuepilot:local .
docker run --rm -p 8000:8000 --env-file .env queuepilot:local   # → http://localhost:8000
```

## 3. Why this way
- **Multi-stage** keeps the final image lean and safe: the Node/pnpm toolchain (only needed to *build*
  the bundle) is discarded — the runtime image is just Python + deps + static files.
- **`uv sync --frozen`** installs the exact locked versions → reproducible, matches local/CI.
- **`--host 0.0.0.0`**: inside a container, `127.0.0.1` is the container's own loopback; binding
  `0.0.0.0` makes the server reachable from the host via the published port (`-p host:container`).
- **`${PORT}`**: PaaS platforms (Render) inject the port to bind; defaulting to 8000 keeps local runs
  simple. Same image, local and cloud (D10 — one deploy target).
- **Secrets via `--env-file` / platform env**, never in the image — a leaked image must not leak keys
  (12-factor config).

## 4. Verify it yourself
```bash
uv run python learn/13_containerization.py
```
**Expected:** an annotated breakdown of the real `Dockerfile` (each instruction → what layer/why) and
`.dockerignore`, plus assertions that the build is genuinely multi-stage, binds `0.0.0.0`, and keeps
`.env` out of the context. It reads the actual repo files, so it proves the shipped setup — not a toy.

## 5. Self-quiz
1. Why copy `package.json`/`uv.lock` and install deps *before* copying the rest of the source?
2. What does a multi-stage build buy you that a single stage doesn't?
3. Why must the server bind `0.0.0.0` (not `127.0.0.1`) inside the container, and why do we pass
   secrets with `--env-file` instead of a `COPY .env`?

<details><summary>Answers</summary>

1. **Layer caching.** The dependency-install layer is keyed on the manifest files; if they're
   unchanged, Docker reuses the cached install on rebuilds and only re-runs the fast source-copy +
   build steps. Copying all source first would bust the cache on every code change.
2. It **separates build-time from run-time**. The build toolchain (Node, pnpm, compilers) lives only
   in the earlier stage; the final image copies just the built artifacts, so it's smaller and has a
   smaller attack surface.
3. `127.0.0.1` inside the container is only reachable *within* the container; `0.0.0.0` binds all
   interfaces so the published port reaches it from the host. `.env` is excluded via `.dockerignore`
   and injected at run so secrets never become an immutable image layer (which could be pushed/shared).
</details>

## 6. Takeaway
A multi-stage Dockerfile turns "runs on my machine" into a single reproducible image that runs the
same locally and on Render — build the frontend in a throwaway Node stage, ship a lean Python runtime,
cache by copying manifests before source, bind `0.0.0.0`, and inject secrets at run time (never bake
them in).
