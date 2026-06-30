"""QueuePilot FastAPI application.

Slice A exposes /health and /analyze. See docs/final-build-plan/03-API-CONTRACT.md.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.analyze.graph_analyzer import get_graph_analyzer
from app.config import get_settings
from app.schemas import AnalyzeRequest, AnalyzeResponse

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
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a support ticket with the Slice B LangGraph workflow.

    Runs the full guarded-copilot graph (retrieve → classify → sentiment →
    assess_missing → score → decide → draft_reply|clarify) and returns a
    populated Slice-B envelope (see 03-API-CONTRACT.md).

    Falls back automatically to the Slice A ``Analyzer`` if the graph raises.
    Raises 422 automatically on request validation failure (e.g. oversized text).
    """
    return get_graph_analyzer().analyze(req.text)
