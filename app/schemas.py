"""API contract models — the binding /analyze request/response shapes.

This is the single source of truth in code for docs/final-build-plan/03-API-CONTRACT.md. The
response envelope is forward-compatible: Slice A populates a subset; later slices fill reserved
fields (sentiment, sla_risk, escalate, clarification, suggested_reply, trace) without shape change.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings


class AnalyzeRequest(BaseModel):
    """Incoming ticket to analyze."""

    text: str
    metadata: dict[str, Any] | None = None

    @field_validator("text")
    @classmethod
    def _non_empty_within_limit(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        limit = get_settings().max_input_chars
        if len(cleaned) > limit:
            raise ValueError(f"text exceeds MAX_INPUT_CHARS ({limit})")
        return cleaned


class SimilarTicket(BaseModel):
    """One retrieved historical neighbor (maps from retrieval Neighbor)."""

    score: float
    queue: str | None = None
    priority: str | None = None
    type: str | None = None
    snippet: str


class AnalyzeResponse(BaseModel):
    """The full, forward-compatible output envelope (see 03-API-CONTRACT.md)."""

    # --- Slice A populates these ---
    category: str | None = None
    queue: str | None = None
    priority: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    similar_tickets: list[SimilarTicket] = Field(default_factory=list)

    # --- reserved; None until the owning slice (B = workflow, C = trace) ---
    sentiment: dict[str, float] | None = None
    sla_risk: float | None = None
    escalate: bool | None = None
    clarification: list[str] | None = None
    suggested_reply: str | None = None
    trace: dict[str, Any] | None = None
