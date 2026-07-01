# 01 — Tech Stack (LOCKED 🔒)

Changing anything here requires explicit user sign-off + a new entry in `05-DECISIONS-LOCKED.md`.

| Layer | Choice | Notes |
|---|---|---|
| Language | **Python 3.11+** | System Python is 3.9 — a fresh venv is required. |
| Env / deps | **uv** | `pyproject.toml`; `uv run` to boot. |
| Lint / types | **ruff** + **mypy** (or pyright) | Must pass clean in CI/local before "done". |
| App shell | **FastAPI** | Serves API + console from the same app (v1). Console is a Vite/React/TypeScript/Tailwind/shadcn SPA built to static assets and mounted by FastAPI — same origin, one deploy target (refines D13; build paused pending UI-design session). |
| Orchestration | **LangGraph** | Introduced in Slice B; Slice A uses a plain baseline. |
| Vector DB | **Pinecone** | **Single sparse-dense index** (current recommended hybrid approach). |
| Dense embeddings | **Gemini** | Fixed dimension, pinned when A3 lands; behind an `Embedder` protocol. |
| Sparse vectors | **BM25 via `pinecone-text`** | Generated locally; fitted params persisted. |
| Score fusion | **`hybrid_score_norm(alpha)`** | Normalize sparse+dense at query time; `alpha` config-driven. |
| Chat LLM | **Swappable provider registry** | Default cheap/fast (Groq/Gemini); **OpenAI a provable drop-in**. |
| Eval / tracing | **LangSmith** | Tracing in C; offline+online eval in D. |
| Deploy | **Docker → Render** | Same app serves UI + API. |
| Access (v1) | Invite code + signed HTTP-only cookie + rate limiting | Slice E. |

## Deferred tech (NOT in v1)
GraphQL · Azure / Azure Service Bus · OpenAI-only · voice (ASR/TTS) · full auth · multi-tenant.
These are out of scope for v1; building them now would dilute the core focus of the project.

## Hard rules
- Once the Gemini embedding **dimension** is chosen for the index, it is fixed; changing it forces a
  full reindex. Pin it in config and document in `docs/learn/01-embeddings.md`.
- All provider keys stay **server-side** via `pydantic-settings`. `.env` is gitignored;
  `.env.example` documents every key.
