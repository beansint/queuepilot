"""Pure helper for building the ``trace`` summary in ``AnalyzeResponse`` (Slice C).

Kept separate from ``graph_analyzer.py`` so the URL/run-id extraction logic is testable
without a live LangSmith run — callers pass in already-extracted primitives (or a fake
run-tree-like object) rather than this module reaching into LangSmith itself.
"""

from __future__ import annotations

from typing import Any


def build_trace_summary(
    run_tree: Any,
    latency_ms: float | None,
    project: str | None,
    enabled: bool,
) -> dict[str, Any]:
    """Return the ``trace`` dict for ``AnalyzeResponse`` from a run tree (or ``None``).

    Never raises — any failure extracting fields from *run_tree* falls back to a
    disabled-shaped summary so tracing issues never break ``/analyze``.

    Args:
        run_tree: A LangSmith ``RunTree`` (or any object exposing ``.id`` and a
            ``.get_url()`` method / attribute-compatible fake for tests). May be ``None``.
        latency_ms: Wall-clock latency of the traced call, in milliseconds.
        project: The LangSmith project name traces were sent to.
        enabled: Whether tracing was actually active for this call (settings flag AND key
            present). When ``False``, the run tree is ignored and a minimal disabled
            summary is returned.

    Returns:
        When disabled (or *run_tree* is ``None``): ``{"enabled": False}`` — the minimal
        shape, so callers/tests can assert equality without enumerating every key.
        When enabled: ``{"enabled": True, "run_id": str | None, "url": str | None,
        "latency_ms": float | None, "project": str | None}``.
    """
    if not enabled or run_tree is None:
        return {"enabled": False}

    try:
        run_id = str(run_tree.id) if getattr(run_tree, "id", None) is not None else None
    except Exception:
        run_id = None

    url: str | None = None
    try:
        get_url = getattr(run_tree, "get_url", None)
        if callable(get_url):
            url = get_url()
    except Exception:
        url = None

    return {
        "enabled": True,
        "run_id": run_id,
        "url": url,
        "latency_ms": latency_ms,
        "project": project,
    }
