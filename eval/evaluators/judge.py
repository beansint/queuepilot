"""LLM-as-judge evaluator for ``suggested_reply`` quality (D6).

Pinned to Gemini regardless of the chat model under test (Groq generates the reply;
letting it grade itself would be self-preference bias — see 11-SLICE-D-DESIGN.md).
Degrades gracefully to a skip dict (``score: None``) when no Gemini key is configured,
or when the example has no ``suggested_reply`` to grade (e.g. the clarify / edge-case
path). LangSmith's ``evaluate()`` runner rejects a bare ``None`` return (see
``langsmith.evaluation.evaluator._format_evaluator_result``), so we never return ``None``
directly — only a dict, always keyed ``reply_quality`` with a numeric-typed ``score``
(``None`` on skip, ``[0, 1]`` otherwise).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langsmith import traceable

from app.config import get_settings
from app.providers.chat import GeminiChat
from eval.settings import get_eval_settings

_logger = logging.getLogger(__name__)

_JUDGE_SYSTEM_PROMPT = (
    "You are an impartial quality judge for customer-support ticket replies. "
    "Score the CANDIDATE REPLY on two dimensions, each on a 1-5 integer scale:\n"
    "  - groundedness: is the reply supported by / consistent with the RETRIEVED NEIGHBORS "
    "(similar historical tickets), rather than inventing unsupported claims?\n"
    "  - helpfulness: does the reply directly and usefully address the TICKET?\n"
    "Respond with ONLY a JSON object: "
    '{"groundedness": <1-5 int>, "helpfulness": <1-5 int>, "rationale": "<one or two sentences>"}.'
)


def _build_judge() -> GeminiChat | None:
    """Build the Gemini judge model directly (bypasses ``get_chat_model``/``CHAT_PROVIDER``).

    Returns ``None`` when no Gemini API key is configured, so callers can no-op rather
    than raise.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    return GeminiChat(api_key=settings.gemini_api_key, model=get_eval_settings().judge_model)


def _clamp_1_to_5(value: Any) -> int:
    """Clamp a possibly out-of-range / non-int judge score into ``[1, 5]``."""
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        as_int = 1
    return max(1, min(5, as_int))


def _normalize(score_1_to_5: int) -> float:
    """Map a 1-5 score to ``[0, 1]`` (1 -> 0.0, 5 -> 1.0)."""
    return (score_1_to_5 - 1) / 4.0


@traceable(run_type="chain", name="eval.reply_quality")
def reply_quality(
    inputs: dict[str, Any], outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """LangSmith evaluator: judge ``outputs["suggested_reply"]`` for groundedness + helpfulness.

    Returns the skip dict ``{"key": "reply_quality", "score": None, "comment": <reason>}``
    when there is no reply to grade (e.g. the clarify path) or when no Gemini key is
    configured. Otherwise returns ``{"key": "reply_quality", "score": <mean of both dims
    normalized to [0,1]>, "comment": <rationale>}``.
    """
    suggested_reply = outputs.get("suggested_reply")
    if not suggested_reply or not str(suggested_reply).strip():
        return {"key": "reply_quality", "score": None, "comment": "no suggested_reply"}

    judge = _build_judge()
    if judge is None:
        _logger.warning("reply_quality: no Gemini API key configured; skipping judge.")
        return {
            "key": "reply_quality",
            "score": None,
            "comment": "no Gemini API key configured",
        }

    ticket_text = inputs.get("text", "")
    neighbors = outputs.get("similar_tickets") or []
    neighbors_block = json.dumps(neighbors, default=str)[:4000]

    user_prompt = (
        f"TICKET:\n{ticket_text}\n\n"
        f"RETRIEVED NEIGHBORS (JSON):\n{neighbors_block}\n\n"
        f"CANDIDATE REPLY:\n{suggested_reply}"
    )

    try:
        result = judge.complete_json(_JUDGE_SYSTEM_PROMPT, user_prompt)
        groundedness = _clamp_1_to_5(result.get("groundedness"))
        helpfulness = _clamp_1_to_5(result.get("helpfulness"))
        rationale = str(result.get("rationale") or "")
        mean_normalized = (_normalize(groundedness) + _normalize(helpfulness)) / 2.0
    except Exception as exc:
        # Any judge failure (network/rate-limit error, non-JSON output raising ValueError,
        # etc.) must degrade to the documented skip contract, never propagate. The comment
        # carries ONLY the exception class name — never str(exc), which could echo request
        # payloads or key material back into a LangSmith-visible comment field.
        _logger.warning("reply_quality: judge call failed (%s)", type(exc).__name__)
        return {
            "key": "reply_quality",
            "score": None,
            "comment": f"judge error: {type(exc).__name__}",
        }

    return {"key": "reply_quality", "score": mean_normalized, "comment": rationale}
