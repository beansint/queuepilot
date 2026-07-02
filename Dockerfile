# syntax=docker/dockerfile:1
#
# QueuePilot — one image serves the React console + FastAPI API (D10/D13).
# Multi-stage: a Node stage builds the frontend bundle; a lean Python stage runs it.

# ---- Stage 1: build the React console → /frontend/dist ----------------------
FROM node:20-alpine AS frontend
WORKDIR /frontend
# Copy only the manifests first so `pnpm install` is cached until deps change
# (layer caching: this RUN is skipped on rebuilds when package.json/lock are unchanged).
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@9 --activate && pnpm install --frozen-lockfile
# Now bring in the rest of the source and produce the static bundle (tsc -b && vite build).
COPY frontend/ ./
RUN pnpm build

# ---- Stage 2: Python runtime (uv) — API + built console --------------------
FROM python:3.12-slim AS runtime
# uv gives fast, reproducible installs straight from uv.lock. Pin the uv version (not :latest)
# so a rebuild can't silently pull a uv that changes resolution / breaks `uv sync --frozen`.
COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /uvx /bin/
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
# Install ONLY dependencies first (project sets [tool.uv] package=false, so there is no
# local package build). Caches until pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# Application code + the runtime BM25 artifact + the built console from stage 1.
COPY app/ ./app/
COPY data/artifacts/ ./data/artifacts/
COPY --from=frontend /frontend/dist ./frontend/dist
# Render (and most PaaS) inject $PORT; default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000
# Bind 0.0.0.0 so the server is reachable from OUTSIDE the container (localhost inside
# the container is not the host). Run the venv's uvicorn directly (no uv wrapper at runtime).
CMD ["sh", "-c", ".venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
