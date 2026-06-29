"""QueuePilot FastAPI application.

Slice A exposes /health and (from A8) /analyze. See docs/final-build-plan/03-API-CONTRACT.md.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings

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
