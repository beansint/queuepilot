"""QueuePilot FastAPI application.

Slice A exposes /health and /analyze. See docs/final-build-plan/03-API-CONTRACT.md.
Slice C adds ?explain=true on /analyze and a best-effort SPA serve stub (C6) — the
frontend is paused, so this degrades to a placeholder page when frontend/dist is absent
(the case in CI/tests).
"""

from __future__ import annotations

import hmac
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from langsmith import Client
from pydantic import BaseModel

from app.analyze.graph_analyzer import get_graph_analyzer
from app.auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    auth_required,
    is_request_authenticated,
    issue_cookie_value,
    require_auth,
)
from app.config import get_settings
from app.eval_api import router as eval_router
from app.feedback import get_feedback_client, submit_feedback
from app.graphql import build_graphql_router
from app.ratelimit import login_rate_limit, rate_limit
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


class LoginRequest(BaseModel):
    """Body for ``POST /login`` — the single shared invite code (Slice E — D16)."""

    code: str


@app.post("/login", dependencies=[Depends(login_rate_limit)])
def login(req: LoginRequest, response: Response) -> dict[str, bool]:
    """Exchange the shared invite code for a signed HTTP-only session cookie.

    A no-op ``{"ok": True}`` when auth is unconfigured (graceful-degradation — see
    ``app.auth.auth_required``). Otherwise ``401`` on a wrong code; on a match, sets
    ``qp_session`` (HTTP-only, ``SameSite=Lax``, ``Secure`` outside development) and
    returns ``{"ok": True}``.
    """
    settings = get_settings()
    if not auth_required():
        return {"ok": True}
    # settings.invite_code is guaranteed non-empty here (auth_required() checked both).
    # Compare as bytes: hmac.compare_digest raises TypeError on non-ASCII str inputs, so a
    # code with non-ASCII characters would otherwise 500 instead of returning 401.
    submitted = req.code.encode("utf-8")
    expected = (settings.invite_code or "").encode("utf-8")
    if not hmac.compare_digest(submitted, expected):
        raise HTTPException(status_code=401, detail="invalid invite code")
    response.set_cookie(
        key=COOKIE_NAME,
        value=issue_cookie_value(),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=(settings.environment != "development"),
        path="/",
    )
    return {"ok": True}


@app.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    """Clear the session cookie. Always returns ``{"ok": True}``."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/auth/status")
def auth_status(request: Request) -> dict[str, bool]:
    """Report whether auth is required and whether this request is authenticated.

    Always open (never gated by ``require_auth``) — the frontend needs this to decide
    whether to show the login gate at all.
    """
    required = auth_required()
    authenticated = required and is_request_authenticated(request)
    return {"required": required, "authenticated": authenticated}


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    dependencies=[Depends(require_auth), Depends(rate_limit)],
)
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


@lru_cache(maxsize=1)
def _get_feedback_client() -> Client | None:
    """Build (and cache) the LangSmith client used by ``POST /feedback``.

    Cached like ``app.analyze.graph_analyzer.get_graph_analyzer`` — building a fresh
    ``langsmith.Client()`` (and its connection pool/threads) on every request is wasteful
    since LangSmith config doesn't change within a process lifetime. Returns ``None``
    (also cached) when LangSmith is unconfigured, so unconfigured deployments no-op cheaply
    on every call rather than re-attempting client construction each time.
    """
    return get_feedback_client()


@app.post("/feedback", dependencies=[Depends(require_auth), Depends(rate_limit)])
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


# ---------------------------------------------------------------------------
# GraphQL (Slice F — D17): additive /graphql over the same services as REST.
# Mounted BEFORE the frontend routes so the SPA mount never shadows it. Gated +
# rate-limited by the same dependencies as REST /analyze (inside build_graphql_router).
# ---------------------------------------------------------------------------
app.include_router(build_graphql_router(), prefix="/graphql")

# ---------------------------------------------------------------------------
# Eval snapshots (D8 follow-up): additive /eval/snapshots surface over the
# committed eval/snapshots/*.json cards, gated by the same require_auth +
# rate_limit dependencies as REST /analyze. Mounted before the frontend routes
# for the same reason as /graphql above.
# ---------------------------------------------------------------------------
app.include_router(eval_router)

_register_frontend_routes(app)
