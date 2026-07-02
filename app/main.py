"""QueuePilot FastAPI application.

Slice A exposes /health and /analyze. See docs/final-build-plan/03-API-CONTRACT.md.
Slice C adds ?explain=true on /analyze and a best-effort SPA serve stub (C6) — the
frontend is paused, so this degrades to a placeholder page when frontend/dist is absent
(the case in CI/tests).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from langsmith import Client

from app.analyze.graph_analyzer import get_graph_analyzer
from app.config import get_settings
from app.feedback import get_feedback_client, submit_feedback
from app.schemas import AnalyzeRequest, AnalyzeResponse, FeedbackRequest

app = FastAPI(
    title="QueuePilot",
    description="Agentic AI ticketing system — hybrid retrieval + guarded copilot workflow.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    req: AnalyzeRequest,
    explain: bool = Query(
        False,
        description=(
            "When true, populate the reserved `debug` field with node rationales, "
            "retrieval snippets, and confidence/SLA scoring breakdowns (Slice C)."
        ),
    ),
) -> AnalyzeResponse:
    """Analyze a support ticket with the Slice B LangGraph workflow.

    Runs the full guarded-copilot graph (retrieve → classify → sentiment →
    assess_missing → score → decide → draft_reply|clarify) and returns a
    populated Slice-B envelope (see 03-API-CONTRACT.md).

    Falls back automatically to the Slice A ``Analyzer`` if the graph raises.
    Raises 422 automatically on request validation failure (e.g. oversized text).
    """
    return get_graph_analyzer().analyze(req.text, explain=explain)


def _get_feedback_client() -> Client | None:
    """Lazily build the LangSmith client used by ``POST /feedback``.

    Not cached: ``get_feedback_client()`` is cheap (env export + ``Client()`` construction)
    and re-checking settings each call keeps the endpoint responsive to config changes
    without a stale singleton. Returns ``None`` when LangSmith is unconfigured.
    """
    return get_feedback_client()


@app.post("/feedback")
def feedback(req: FeedbackRequest) -> dict[str, bool]:
    """Submit human feedback (thumbs + optional correction) on a prior ``/analyze`` run.

    See docs/final-build-plan/03-API-CONTRACT.md (POST /feedback, Slice D — D15) and
    docs/final-build-plan/11-SLICE-D-DESIGN.md (D9). Best-effort: always returns
    ``{"ok": True}``, even when LangSmith is unconfigured or the call fails.
    """
    return submit_feedback(req, client=_get_feedback_client())


# ---------------------------------------------------------------------------
# Frontend serve stub (C6) — frontend work is PAUSED; this is a graceful stub only.
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_FRONTEND_INDEX = _FRONTEND_DIST / "index.html"

_PLACEHOLDER_HTML = """\
<!doctype html>
<html>
  <head><title>QueuePilot</title></head>
  <body style="font-family: sans-serif; max-width: 40rem; margin: 4rem auto;">
    <h1>QueuePilot API is running</h1>
    <p>The frontend has not been built yet. Run <code>npm run build</code> in
    <code>frontend/</code>, then restart the server, to serve the dashboard here.</p>
    <p>In the meantime: <a href="/docs">/docs</a> · <a href="/health">/health</a></p>
  </body>
</html>
"""


def _register_frontend_routes(fastapi_app: FastAPI) -> None:
    """Serve the built SPA when present; otherwise a graceful placeholder page.

    Registered last so ``/health``, ``/analyze``, and ``/docs`` are matched first —
    FastAPI checks normal path operations before falling through to the frontend
    routes (``app.frontend``) / catch-all placeholder below.
    """
    if _FRONTEND_INDEX.is_file() and hasattr(fastapi_app, "frontend"):
        fastapi_app.frontend("/", directory=_FRONTEND_DIST, check_dir=False)
        return

    if _FRONTEND_INDEX.is_file():
        # Installed FastAPI predates `app.frontend`; fall back to StaticFiles.
        from fastapi.staticfiles import StaticFiles

        fastapi_app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
        return

    # No build present (e.g. CI/tests) — serve a graceful placeholder at root only.
    # Deliberately NOT a `{full_path:path}` catch-all: that would greedily match every
    # GET request (including GET on POST-only endpoints like /analyze), shadowing
    # FastAPI's normal 404/405 handling for unmatched routes.
    @fastapi_app.get("/", include_in_schema=False)
    def _frontend_placeholder() -> HTMLResponse:
        return HTMLResponse(content=_PLACEHOLDER_HTML, status_code=200)


_register_frontend_routes(app)
