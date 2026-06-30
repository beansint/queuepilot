"""QueuePilot FastAPI application.

Slice A exposes /health and /analyze. See docs/final-build-plan/03-API-CONTRACT.md.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.analyze.baseline import get_analyzer
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
    """Analyze a support ticket: retrieve similar historical cases and derive labels.

    Returns a forward-compatible envelope (see 03-API-CONTRACT.md).  Slice A populates
    category, queue, priority, confidence, and similar_tickets; reserved fields are null
    until their owning slice lands.

    Raises 422 automatically on request validation failure (e.g. oversized text).
    """
    return get_analyzer().analyze(req.text)
