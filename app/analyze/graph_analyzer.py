"""GraphAnalyzer — Slice B composition root that drives the LangGraph workflow.

Replaces the Slice A ``Analyzer`` as the entry point for ``POST /analyze``.
The public interface is identical — ``analyze(text) -> AnalyzeResponse`` — so
``app/main.py`` needs only one import swap; the HTTP contract is unchanged.

Safety contract:
  If the graph raises any exception, falls back to the Slice A
  ``Analyzer().analyze(text)`` so ``/analyze`` never returns 500 due to a
  graph-level failure.  Node-level failures are already handled inside each
  node (see ``app/analyze/graph.py``).
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any

from langsmith import traceable, tracing_context
from langsmith.run_helpers import get_current_run_tree

from app.analyze.baseline import Analyzer
from app.analyze.graph import TicketState, build_default_graph
from app.analyze.trace import build_trace_summary
from app.config import get_settings
from app.retrieval.hybrid import to_similar_tickets
from app.schemas import AnalyzeResponse

_logger = logging.getLogger(__name__)


class GraphAnalyzer:
    """Drive the LangGraph workflow and map its final ``TicketState`` to ``AnalyzeResponse``.

    The compiled graph is injected via ``__init__`` so tests can supply a lightweight
    fake without touching the network.  Production callers should use ``from_settings()``
    or the ``get_graph_analyzer()`` singleton.
    """

    def __init__(self, graph: Any) -> None:
        self._graph: Any = graph

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> GraphAnalyzer:
        """Build a ``GraphAnalyzer`` backed by the live dependency graph.

        Deferred construction (not at import) so the app boots without keys /
        BM25 artifact present.  Raises if any required key or artifact is missing.
        """
        return cls(graph=build_default_graph())

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------

    def analyze(self, text: str, *, explain: bool = False) -> AnalyzeResponse:
        """Invoke the LangGraph workflow for *text* and map the final state to an envelope.

        The graph runs: retrieve → classify → sentiment → assess_missing → score
        → decide → (draft_reply | clarify | END).  All Slice-B reserved fields
        in ``AnalyzeResponse`` are populated from the resulting ``TicketState``.

        On any hard graph-level exception the method falls back to the Slice A
        ``Analyzer.from_settings().analyze(text)`` and logs the error, so the
        endpoint always returns a valid ``AnalyzeResponse``.

        Args:
            text: Ticket text (assumed pre-validated by ``AnalyzeRequest``).
            explain: When ``True``, populate ``AnalyzeResponse.debug`` from the
                in-app accumulator (``reasoning``/breakdowns) built up in ``TicketState``
                by the graph nodes. Never reconstructed from LangSmith.

        Returns:
            Populated ``AnalyzeResponse``. ``trace`` reflects LangSmith tracing status
            (Slice C) — ``{"enabled": False}`` when tracing is off or no key is set.
        """
        settings = get_settings()
        tracing_enabled = bool(settings.langsmith_tracing and settings.langsmith_api_key)

        captured: dict[str, Any] = {}

        @traceable(run_type="chain", name="GraphAnalyzer.analyze")
        def _run(ticket_text: str) -> TicketState:
            if tracing_enabled:
                try:
                    captured["run_tree"] = get_current_run_tree()
                except Exception:
                    _logger.debug(
                        "GraphAnalyzer.analyze: could not capture run tree", exc_info=True
                    )
            return self._graph.invoke({"text": ticket_text})  # type: ignore[no-any-return]

        start = time.perf_counter()
        try:
            with tracing_context(enabled=tracing_enabled):
                state: TicketState = _run(text)
        except Exception:
            _logger.exception(
                "GraphAnalyzer.analyze: graph.invoke raised an exception; "
                "falling back to Slice A Analyzer"
            )
            return Analyzer.from_settings().analyze(text)
        latency_ms = (time.perf_counter() - start) * 1000.0

        try:
            trace = build_trace_summary(
                captured.get("run_tree"),
                latency_ms,
                settings.langsmith_project,
                tracing_enabled,
            )
        except Exception:
            _logger.exception("GraphAnalyzer.analyze: failed to build trace summary")
            trace = {"enabled": False}

        # Build the envelope from the final TicketState.
        neighbors = state.get("neighbors") or []
        confidence_raw = float(state.get("confidence", 0.0))
        # Defensive clamp — guards against a scoring bug producing out-of-range values.
        confidence = max(0.0, min(1.0, confidence_raw))

        # ``clarification`` is only set when the clarify branch ran; treat an empty
        # list the same as absent (the API contract says null when not on clarify path).
        raw_clarification = state.get("clarification")
        clarification: list[str] | None = list(raw_clarification) if raw_clarification else None

        debug: dict[str, Any] | None = None
        if explain:
            debug = self._build_debug(state, neighbors)

        return AnalyzeResponse(
            category=state.get("category"),
            queue=state.get("queue"),
            priority=state.get("priority"),
            confidence=confidence,
            similar_tickets=to_similar_tickets(neighbors),
            # Slice-B reserved fields (now populated)
            sentiment=state.get("sentiment"),
            sla_risk=state.get("sla_risk"),
            escalate=state.get("escalate"),
            clarification=clarification,
            suggested_reply=state.get("suggested_reply"),
            # Slice C
            trace=trace,
            debug=debug,
        )

    # ------------------------------------------------------------------
    # --explain support (C4)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_debug(state: TicketState, neighbors: list[Any]) -> dict[str, Any]:
        """Assemble ``AnalyzeResponse.debug`` from the final ``TicketState``.

        Pure mapping — no LLM calls, no LangSmith. Reads the in-app accumulator
        fields (``reasoning``, ``confidence_breakdown``, ``sla_breakdown``) that the
        graph nodes populate as they run (see ``app/analyze/graph.py``).
        """
        reasoning: dict[str, str] = dict(state.get("reasoning") or {})
        nodes = [{"name": name, "rationale": rationale} for name, rationale in reasoning.items()]
        retrieval = [
            {
                "score": n.score,
                "queue": n.queue,
                "priority": n.priority,
                "type": n.type,
                "snippet": n.snippet,
            }
            for n in neighbors
        ]
        return {
            "nodes": nodes,
            "retrieval": retrieval,
            "confidence_breakdown": dict(state.get("confidence_breakdown") or {}),
            "sla_breakdown": dict(state.get("sla_breakdown") or {}),
            "decision": state.get("decision"),
        }


# ---------------------------------------------------------------------------
# Lazy singleton for production use
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_graph_analyzer() -> GraphAnalyzer:
    """Return a lazily-built singleton ``GraphAnalyzer`` (constructed on first call).

    Mirrors ``get_analyzer()`` — the ``lru_cache`` ensures ``build_default_graph()``
    is called at most once per process.  If the first call raises, the exception
    propagates and the function is NOT cached so subsequent calls will retry.
    """
    return GraphAnalyzer.from_settings()
