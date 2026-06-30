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
from functools import lru_cache
from typing import Any

from app.analyze.baseline import Analyzer
from app.analyze.graph import TicketState, build_default_graph
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

    def analyze(self, text: str) -> AnalyzeResponse:
        """Invoke the LangGraph workflow for *text* and map the final state to an envelope.

        The graph runs: retrieve → classify → sentiment → assess_missing → score
        → decide → (draft_reply | clarify | END).  All Slice-B reserved fields
        in ``AnalyzeResponse`` are populated from the resulting ``TicketState``.

        On any hard graph-level exception the method falls back to the Slice A
        ``Analyzer.from_settings().analyze(text)`` and logs the error, so the
        endpoint always returns a valid ``AnalyzeResponse``.

        Args:
            text: Ticket text (assumed pre-validated by ``AnalyzeRequest``).

        Returns:
            Populated ``AnalyzeResponse``.  ``trace`` remains ``None`` until Slice C.
        """
        try:
            state: TicketState = self._graph.invoke({"text": text})
        except Exception:
            _logger.exception(
                "GraphAnalyzer.analyze: graph.invoke raised an exception; "
                "falling back to Slice A Analyzer"
            )
            return Analyzer.from_settings().analyze(text)

        # Build the envelope from the final TicketState.
        neighbors = state.get("neighbors") or []
        confidence_raw = float(state.get("confidence", 0.0))
        # Defensive clamp — guards against a scoring bug producing out-of-range values.
        confidence = max(0.0, min(1.0, confidence_raw))

        # ``clarification`` is only set when the clarify branch ran; treat an empty
        # list the same as absent (the API contract says null when not on clarify path).
        raw_clarification = state.get("clarification")
        clarification: list[str] | None = list(raw_clarification) if raw_clarification else None

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
            trace=None,
        )


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
