# 00 — Tooling & app skeleton (uv, pydantic-settings, FastAPI)

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `A1` · Runnable companion: `uv run python learn/00_config_demo.py`

## 1. Concept
Three foundations under every Python AI service:
- **`uv`** — a fast package/venv manager. `pyproject.toml` declares deps; `uv sync` builds a locked
  `.venv`; `uv run <cmd>` runs inside it. Replaces `pip` + `venv` + `pip-tools` with one tool.
- **`pydantic-settings`** — typed configuration loaded from the environment / `.env`. You declare a
  `Settings` class with typed fields; it validates and coerces env vars at startup, so a missing or
  malformed value fails loudly instead of surfacing as a `None` deep in a request.
- **FastAPI** — an ASGI web framework. You attach functions to routes (`@app.get("/health")`); it
  handles validation, serialization, and OpenAPI docs.

## 2. In QueuePilot
- `pyproject.toml` — deps + `ruff`/`mypy`/`pytest` config; `[tool.uv] package = false` (we're an
  app, not a library).
- `app/config.py` — the `Settings` class + a cached `get_settings()`. **All** config (keys, caps,
  `hybrid_alpha`) flows through here; nothing reads `os.environ` directly.
- `app/main.py` — the FastAPI app and `GET /health`.

## 3. Why this way
- **Centralized, typed config** keeps provider keys server-side and makes the "what's configurable"
  surface one file — important when keys (`GEMINI_API_KEY`, `PINECONE_API_KEY`) land in A3/A5/A7.
  See `01-TECH-STACK-LOCKED.md` (keys are server-side only) and `02-DATA-MODEL.md` (`EMBED_DIM`
  pinned later).
- **`get_settings()` is `@lru_cache`d** so settings are parsed once, not per request.
- **`uv` over pip** for reproducibility (a committed lockfile) and speed.

## 4. Verify it yourself
```bash
uv run python learn/00_config_demo.py
```
**Expected:** the demo prints the loaded settings with **secrets redacted** (showing only whether a
key is set, never its value), and demonstrates that `get_settings()` returns the *same cached object*
twice. This proves config is typed, centralized, and not re-parsed per call.

## 5. Self-quiz
1. Why route every config value through `Settings` instead of calling `os.environ.get` where needed?
2. What does `[tool.uv] package = false` change, and why is it right for this repo?
3. Why is `get_settings()` cached, and when would that bite you in a test?

<details><summary>Answers</summary>

1. One typed, validated surface: values are coerced/validated once at startup (fail fast), secrets
   stay in one place, and there's a single list of "what's configurable." Scattered `os.environ`
   reads are untyped, unvalidated, and easy to leak.
2. It tells `uv` we're an application, not an installable package — so it doesn't need a build
   backend or to "install" our code; it just manages the venv + deps. Right because we ship a
   service, not a library on PyPI.
3. It parses the env once and reuses the object. In tests that change env vars between cases you must
   clear the cache (`get_settings.cache_clear()`) or the first-loaded values persist.

</details>

## 6. Takeaway
"Config is a typed, cached, server-side boundary — one `Settings` class, validated at startup, so a
bad env var fails loudly instead of leaking a `None` into a request."
