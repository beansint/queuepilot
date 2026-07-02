"""POST /feedback handler — human-feedback flywheel (Slice D — D9).

Best-effort integration with LangSmith: attaches thumbs feedback to a prior ``/analyze``
trace (join key ``run_id`` == Slice C's ``trace.run_id``) and, when a human ``correction``
is supplied, appends a corrected example to the ``queuepilot-feedback`` dataset so real
corrections become future eval data (the "flywheel").

This module never blocks or fails the caller: any LangSmith error is logged and the
handler still returns ``{"ok": True}``. See docs/final-build-plan/11-SLICE-D-DESIGN.md
(D9) and docs/final-build-plan/03-API-CONTRACT.md (POST /feedback).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langsmith import Client

from app.config import Settings, get_settings
from app.schemas import FeedbackRequest

_logger = logging.getLogger(__name__)

_FEEDBACK_DATASET_NAME = "queuepilot-feedback"


def _ensure_langsmith_env(settings: Settings) -> None:
    """Export LangSmith config from ``Settings`` (pydantic-settings/.env) to ``os.environ``.

    Mirrors ``app.analyze.graph_analyzer._ensure_langsmith_env`` — the ``langsmith`` SDK
    reads its configuration directly from the process environment (``LANGSMITH_TRACING`` /
    ``LANGSMITH_API_KEY`` / ``LANGSMITH_PROJECT`` / ``LANGSMITH_ENDPOINT``), not from our
    ``Settings`` object, so a ``.env``-only value would otherwise never reach the SDK. This
    is a no-op when tracing is off, and never raises (missing values are simply skipped).
    """
    if not settings.langsmith_tracing:
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint


def get_feedback_client() -> Client | None:
    """Build a LangSmith ``Client`` for feedback submission, or ``None`` when unconfigured.

    Returns ``None`` (rather than raising) when tracing is disabled or no API key is
    configured, so the caller can gracefully no-op — feedback is best-effort and must
    never block ``POST /feedback``.
    """
    settings = get_settings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return None
    _ensure_langsmith_env(settings)
    try:
        return Client()
    except Exception:
        _logger.exception("get_feedback_client: failed to construct LangSmith Client")
        return None


def submit_feedback(req: FeedbackRequest, *, client: Client | None = None) -> dict[str, bool]:
    """Submit human feedback to LangSmith and, optionally, the correction flywheel dataset.

    Best-effort: any LangSmith failure (client unconfigured, network error, bad run id)
    is logged and swallowed — this call must never raise or block the caller.

    Args:
        req: Validated feedback body (``run_id``, ``score``, optional ``correction``/``comment``).
        client: LangSmith client to use. When ``None`` (LangSmith unconfigured), this is a
            logged no-op.

    Returns:
        ``{"ok": True}`` always.
    """
    if client is None:
        _logger.warning(
            "submit_feedback: LangSmith unconfigured — no-op for run_id=%s", req.run_id
        )
        return {"ok": True}

    try:
        client.create_feedback(
            req.run_id,
            key="user_thumbs",
            score=float(req.score),
            comment=req.comment,
            trace_id=req.run_id,
        )
    except Exception:
        _logger.exception("submit_feedback: create_feedback failed for run_id=%s", req.run_id)
        return {"ok": True}

    if req.correction:
        try:
            if not client.has_dataset(dataset_name=_FEEDBACK_DATASET_NAME):
                client.create_dataset(_FEEDBACK_DATASET_NAME)
            # `text` is optional (D15 additive field, app/schemas.py) — when the caller
            # supplies the original ticket text, include it in `inputs` so this example is
            # actually usable by eval.dataset's `analyze_target` (which needs
            # `inputs["text"]`), not just a `run_id` join key. Still best-effort: falls
            # back to the run_id-only shape when `text` is absent.
            inputs: dict[str, Any] = {"run_id": req.run_id}
            if req.text:
                inputs = {"text": req.text, "run_id": req.run_id}
            client.create_examples(
                dataset_name=_FEEDBACK_DATASET_NAME,
                examples=[{"inputs": inputs, "outputs": req.correction}],
            )
        except Exception:
            _logger.exception(
                "submit_feedback: correction flywheel failed for run_id=%s", req.run_id
            )

    return {"ok": True}
