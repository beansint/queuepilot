"""LangSmith ``Client`` factory for the eval package.

Reuses ``app.config.Settings`` for the LangSmith env vars (single source of truth for
credentials) and exports them to ``os.environ`` exactly like
``app.analyze.graph_analyzer._ensure_langsmith_env`` does, since the ``langsmith`` SDK
reads its configuration directly from the process environment, not from our settings
object.
"""

from __future__ import annotations

import logging
import os

from langsmith import Client

from app.config import Settings, get_settings

_logger = logging.getLogger(__name__)


def _export_langsmith_env(settings: Settings) -> None:
    """Export LangSmith config from ``Settings`` to ``os.environ``.

    Mirrors ``app.analyze.graph_analyzer._ensure_langsmith_env``: a no-op when no API
    key is configured, and never raises (missing values are simply skipped).
    """
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint


def get_langsmith_client() -> Client | None:
    """Return a ``langsmith.Client``, or ``None`` when no API key is configured.

    Never raises on a missing key — callers (dataset upload, experiment runner, online
    eval runner) must degrade gracefully rather than crash when LangSmith isn't set up.
    """
    settings = get_settings()
    if not settings.langsmith_api_key:
        _logger.warning(
            "get_langsmith_client: LANGSMITH_API_KEY not set; returning None "
            "(eval will run offline / skip upload)."
        )
        return None
    _export_langsmith_env(settings)
    return Client()
