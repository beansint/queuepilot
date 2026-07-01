"""learn/08_langsmith_tracing.py — C7: LangSmith tracing / observability.

Companion to docs/learn/08-langsmith-tracing.md. Run:

    uv run python learn/08_langsmith_tracing.py

Proves two things, fully offline (no LANGSMITH_API_KEY, no network):
  1. `tracing_context(enabled=False)` makes `@traceable` a true no-op — the wrapped
     function still runs and returns its value, but there is no run tree to read.
  2. `build_trace_summary` (the real app code that shapes `AnalyzeResponse.trace`)
     produces the disabled-vs-enabled dict shape from a fake run-tree object, exactly
     like `tests/test_trace.py`'s `_FakeRunTree`, including the never-raises guarantee.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langsmith import traceable, tracing_context  # noqa: E402
from langsmith.run_helpers import get_current_run_tree  # noqa: E402

from app.analyze.trace import build_trace_summary  # noqa: E402


@traceable(run_type="chain", name="toy_traced_add")
def toy_traced_add(a: int, b: int) -> int:
    """A tiny @traceable function — mirrors how GraphAnalyzer.analyze wraps its call."""
    return a + b


class _FakeRunTree:
    """Minimal stand-in for a langsmith RunTree — only the attrs build_trace_summary reads.

    Mirrors tests/test_trace.py::_FakeRunTree so this demo proves the same contract the
    unit tests cover.
    """

    def __init__(self, run_id: Any, url: str | None = None, raise_on_url: bool = False) -> None:
        self.id = run_id
        self._url = url
        self._raise_on_url = raise_on_url

    def get_url(self) -> str:
        if self._raise_on_url:
            raise RuntimeError("boom: LangSmith SDK internal error")
        return self._url or ""


def main() -> None:
    print("== C7: LangSmith tracing / observability ==\n")

    # ------------------------------------------------------------------
    # 1. tracing_context(enabled=False) is a true no-op.
    # ------------------------------------------------------------------
    print("-- Part 1: tracing_context(enabled=False) is a no-op --")
    captured: dict[str, Any] = {}
    with tracing_context(enabled=False):
        result = toy_traced_add(2, 3)
        try:
            captured["run_tree"] = get_current_run_tree()
        except Exception as exc:
            captured["run_tree"] = None
            captured["error"] = repr(exc)

    print(f"  toy_traced_add(2, 3) still returned: {result}")
    print(f"  run tree captured while disabled:    {captured.get('run_tree')!r}")
    print("  -> the function executes normally; tracing is skipped entirely, no network call.\n")

    # ------------------------------------------------------------------
    # 2. build_trace_summary — the exact function that shapes
    #    AnalyzeResponse.trace in app/analyze/graph_analyzer.py.
    # ------------------------------------------------------------------
    print("-- Part 2: build_trace_summary (real app code) — disabled vs enabled --")

    disabled = build_trace_summary(
        run_tree=_FakeRunTree("run-should-be-ignored"),
        latency_ms=12.3,
        project="queuepilot",
        enabled=False,
    )
    print(f"  tracing OFF   -> trace = {disabled}")
    assert disabled == {"enabled": False}

    fake_run = _FakeRunTree("abc-123", url="https://smith.langchain.com/r/abc-123")
    enabled = build_trace_summary(
        run_tree=fake_run,
        latency_ms=812.4,
        project="queuepilot",
        enabled=True,
    )
    print(f"  tracing ON    -> trace = {enabled}")
    assert enabled == {
        "enabled": True,
        "run_id": "abc-123",
        "url": "https://smith.langchain.com/r/abc-123",
        "latency_ms": 812.4,
        "project": "queuepilot",
    }

    broken_url = build_trace_summary(
        run_tree=_FakeRunTree("abc-456", raise_on_url=True),
        latency_ms=5.0,
        project="queuepilot",
        enabled=True,
    )
    print(f"  ON + broken   -> trace = {broken_url}   (get_url() raised; never propagates)")
    assert broken_url["enabled"] is True
    assert broken_url["run_id"] == "abc-456"
    assert broken_url["url"] is None

    print()
    print(
        "Conclusion: the same code path runs whether or not LANGSMITH_API_KEY is set — "
        "tracing degrades to {'enabled': False} instead of breaking /analyze, and a broken "
        "run-tree object (e.g. a flaky get_url()) never raises through build_trace_summary."
    )


if __name__ == "__main__":
    main()
