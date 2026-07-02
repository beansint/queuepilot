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

    # --- reserved; None until Slice C, and only populated when ?explain=true ---
    debug: dict[str, Any] | None = None


class FeedbackRequest(BaseModel):
    """Human feedback on a prior ``/analyze`` result (Slice D — D9).

    ``run_id`` is the LangSmith run id returned in a prior ``/analyze`` response's
    ``trace.run_id`` (Slice C); it is the join key between an analysis and its feedback.
    """

    run_id: str
    score: int
    correction: dict[str, Any] | None = None
    comment: str | None = None
    text: str | None = Field(
        default=None,
        description=(
            "Optional original ticket text, additive for the correction flywheel "
            "(D15 note). When present alongside `correction`, it is attached to the "
            "flywheel example's `inputs` next to `run_id` so eval.dataset's "
            "`analyze_target` (which needs `inputs['text']`) can replay flywheel "
            "corrections as usable eval data. Omitting it keeps the pre-existing "
            "`{'run_id': ...}`-only behavior."
        ),
    )

    @field_validator("run_id")
    @classmethod
    def _non_empty_run_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run_id must not be empty")
        return value

    @field_validator("score")
    @classmethod
    def _score_is_thumbs(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("score must be 0 (thumbs down) or 1 (thumbs up)")
        return value
