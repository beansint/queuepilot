"""``evaluate()`` target function wrapping ``GraphAnalyzer.analyze`` (D7).

Kept out of the request path: this module is only imported by the eval runners, never
by ``app/``. The singleton is built lazily so importing this module never requires keys
or a built BM25 artifact until an evaluation actually runs.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.analyze.graph_analyzer import GraphAnalyzer


@lru_cache(maxsize=1)
def _get_analyzer() -> GraphAnalyzer:
    """Build (once per process) the live ``GraphAnalyzer`` used by ``analyze_target``."""
    return GraphAnalyzer.from_settings()


def analyze_target(inputs: dict[str, Any]) -> dict[str, Any]:
    """LangSmith ``evaluate()`` target: run the analyzer and return a plain evaluator-facing dict.

    Args:
        inputs: A dataset example's ``inputs`` dict, e.g. ``{"text": "...", "metadata": {...}}``.

    Returns:
        A dict with the fields the D4-D6 evaluators read: ``queue``, ``priority``,
        ``type``/``category``, ``confidence``, ``similar_tickets`` (as plain dicts), and
        ``suggested_reply``.
    """
    response = _get_analyzer().analyze(inputs["text"])
    return {
        "queue": response.queue,
        "priority": response.priority,
        "type": response.category,
        "category": response.category,
        "confidence": response.confidence,
        "similar_tickets": [st.model_dump() for st in response.similar_tickets],
        "suggested_reply": response.suggested_reply,
    }
