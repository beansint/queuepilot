"""C3 — unit tests for build_trace_summary (pure; no network, no LangSmith calls).

Covers:
  * Disabled path: enabled=False or run_tree=None → minimal {"enabled": False} dict.
  * Enabled path with a fake run tree: run_id/url/latency/project mapped correctly.
  * Never raises: a run_tree whose .get_url() raises still returns a usable dict.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.analyze.trace import build_trace_summary


class _FakeRunTree:
    """Minimal stand-in for a langsmith RunTree — only the attrs build_trace_summary reads."""

    def __init__(self, run_id: Any, url: str | None = None, raise_on_url: bool = False) -> None:
        self.id = run_id
        self._url = url
        self._raise_on_url = raise_on_url

    def get_url(self) -> str:
        if self._raise_on_url:
            raise RuntimeError("boom")
        return self._url or ""


# ---------------------------------------------------------------------------
# Disabled path
# ---------------------------------------------------------------------------


def test_disabled_returns_minimal_shape() -> None:
    result = build_trace_summary(_FakeRunTree("run-1"), 12.3, "queuepilot", enabled=False)
    assert result == {"enabled": False}


def test_none_run_tree_returns_minimal_shape_even_if_enabled() -> None:
    result = build_trace_summary(None, 12.3, "queuepilot", enabled=True)
    assert result == {"enabled": False}


# ---------------------------------------------------------------------------
# Enabled path
# ---------------------------------------------------------------------------


def test_enabled_maps_run_id_url_latency_project() -> None:
    run_tree = _FakeRunTree("abc-123", url="https://smith.langchain.com/r/abc-123")
    result = build_trace_summary(run_tree, 45.6, "queuepilot", enabled=True)
    assert result["enabled"] is True
    assert result["run_id"] == "abc-123"
    assert result["url"] == "https://smith.langchain.com/r/abc-123"
    assert result["latency_ms"] == pytest.approx(45.6)
    assert result["project"] == "queuepilot"


def test_enabled_with_no_id_attr_returns_none_run_id() -> None:
    class _NoId:
        def get_url(self) -> str:
            return "https://example.com"

    result = build_trace_summary(_NoId(), 1.0, "queuepilot", enabled=True)
    assert result["enabled"] is True
    assert result["run_id"] is None


def test_url_extraction_failure_does_not_raise() -> None:
    run_tree = _FakeRunTree("abc-123", raise_on_url=True)
    result = build_trace_summary(run_tree, 1.0, "queuepilot", enabled=True)
    assert result["enabled"] is True
    assert result["run_id"] == "abc-123"
    assert result["url"] is None


def test_never_raises_on_completely_broken_run_tree() -> None:
    class _Broken:
        @property
        def id(self) -> str:
            raise RuntimeError("no id for you")

    result = build_trace_summary(_Broken(), 1.0, "queuepilot", enabled=True)
    assert result["enabled"] is True
    assert result["run_id"] is None
    assert result["url"] is None
