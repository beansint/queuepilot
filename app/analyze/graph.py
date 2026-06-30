"""LangGraph workflow for Slice B (scaffold → classify/sentiment/assess_missing).

Replaces the Slice A `Analyzer` with a `StateGraph` behind the same `/analyze` contract. State
(`TicketState`) threads through nodes; each node returns a partial-state dict that LangGraph merges.

Slice B build order (08-SLICE-B-DESIGN.md):
  B1  — scaffold + ``retrieve`` node.
  B3  — ``classify`` node (LLM picks category/queue/priority from neighbors).
  B5  — ``assess_missing`` node (LLM lists missing ticket details).
  B6  — ``sentiment`` node (LLM scores frustration + negativity).
  B7+ — score, decide, draft_reply, clarify (coming).

Current graph: START → retrieve → classify → sentiment → assess_missing → END.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from app.analyze.baseline import majority_vote
from app.config import get_settings
from app.providers.chat import ChatModel
from app.providers.embeddings import Embedder
from app.retrieval.hybrid import hybrid_score_norm
from app.retrieval.pinecone_store import Neighbor, PineconeStore
from app.retrieval.sparse import BM25SparseEncoder

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM system-prompt constants (module-level for readability + testability)
# ---------------------------------------------------------------------------

CLASSIFY_SYSTEM: str = (
    "You are a support ticket classifier. "
    "Given a ticket and a list of similar historical tickets (with their labels), "
    "choose the best category, queue, and priority for the new ticket. "
    "Return ONLY a JSON object with three keys: "
    '"category" (string or null), "queue" (string or null), "priority" (string or null). '
    "Use the similar tickets as strong label hints. Return null for any field you cannot determine."
)

SENTIMENT_SYSTEM: str = (
    "You are a sentiment analyzer for support tickets. "
    "Assess the emotional tone of the ticket text. "
    "Return ONLY a JSON object with two keys: "
    '"frustration" (float 0.0–1.0, where 0 = calm and 1 = extremely frustrated) and '
    '"negativity" (float 0.0–1.0, where 0 = neutral/positive and 1 = highly negative). '
    "Base the scores on word choice, punctuation, capitalization, and context."
)

ASSESS_MISSING_SYSTEM: str = (
    "You are a support quality reviewer. "
    "Identify important information that is missing from the ticket "
    "but would help resolve it faster. "
    'Return ONLY a JSON object with one key: "missing_info" '
    "(list of short strings, each describing a missing detail, "
    "e.g. 'no error message', 'no account id', 'no steps to reproduce'). "
    "Return an empty list if the ticket contains all necessary information."
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TicketState(TypedDict, total=False):
    """State threaded through the workflow (see 08-SLICE-B-DESIGN.md).

    ``total=False`` so nodes populate fields incrementally; only ``text`` is seeded at invoke time.
    """

    text: str
    neighbors: list[Neighbor]
    category: str | None
    queue: str | None
    priority: str | None
    sentiment: dict[str, float] | None
    missing_info: list[str]
    sla_risk: float | None
    confidence: float
    decision: str
    clarification: list[str]
    suggested_reply: str | None
    escalate: bool


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(
    embedder: Embedder,
    sparse_encoder: BM25SparseEncoder,
    store: PineconeStore,
    chat_model: ChatModel,
    *,
    top_k: int = 5,
    alpha: float | None = None,
) -> Any:
    """Build and compile the workflow graph from injected dependencies.

    All dependencies are injected so the graph is testable with fakes (no network).
    Each LLM node degrades gracefully — a node failure never raises through the graph.
    """
    effective_alpha = alpha if alpha is not None else get_settings().hybrid_alpha

    # ------------------------------------------------------------------
    # Node: retrieve (Slice A hybrid retrieval — no LLM)
    # ------------------------------------------------------------------

    def retrieve(state: TicketState) -> dict[str, Any]:
        """Hybrid-retrieve neighbors for the ticket text (reuses Slice A retrieval)."""
        text = state["text"]
        dense = embedder.embed_query(text)
        sparse = sparse_encoder.encode_query(text)
        weighted_dense, weighted_sparse = hybrid_score_norm(dense, sparse, effective_alpha)
        neighbors = store.hybrid_query(weighted_dense, weighted_sparse, top_k=top_k)
        return {"neighbors": neighbors}

    # ------------------------------------------------------------------
    # Node: classify (B3) — LLM picks category/queue/priority
    # ------------------------------------------------------------------

    def classify(state: TicketState) -> dict[str, Any]:
        """LLM-classify the ticket's category, queue, and priority using neighbor hints.

        Falls back to ``majority_vote`` when the LLM call fails so the graph never stalls.
        """
        text: str = state["text"]
        neighbors: list[Neighbor] = cast(list[Neighbor], state.get("neighbors") or [])

        try:
            hints = "\n".join(
                f"- queue={n.queue!r}  priority={n.priority!r}  type={n.type!r}"
                f"  (score={n.score:.2f})"
                for n in neighbors
            )
            user = f"Ticket:\n{text}\n\nSimilar tickets:\n{hints or '(none retrieved)'}"
            result = chat_model.complete_json(CLASSIFY_SYSTEM, user)
            return {
                "category": result.get("category"),
                "queue": result.get("queue"),
                "priority": result.get("priority"),
            }
        except Exception:
            _logger.exception("classify node: LLM call failed; falling back to majority_vote")
            fb_queue, fb_priority, fb_category, _ = majority_vote(neighbors)
            return {"category": fb_category, "queue": fb_queue, "priority": fb_priority}

    # ------------------------------------------------------------------
    # Node: sentiment (B6) — LLM scores frustration + negativity
    # ------------------------------------------------------------------

    def sentiment(state: TicketState) -> dict[str, Any]:
        """LLM-score the ticket's emotional tone (frustration and negativity in [0, 1]).

        Falls back to ``{"sentiment": None}`` on any error so downstream nodes see a safe value.
        """
        text: str = state["text"]
        try:
            result = chat_model.complete_json(SENTIMENT_SYSTEM, text)
            frustration = float(result.get("frustration", 0.0))
            negativity = float(result.get("negativity", 0.0))
            # Clamp both scores to [0, 1] in case the model returns out-of-range values.
            frustration = max(0.0, min(1.0, frustration))
            negativity = max(0.0, min(1.0, negativity))
            return {"sentiment": {"frustration": frustration, "negativity": negativity}}
        except Exception:
            _logger.exception("sentiment node: LLM call failed; returning None")
            return {"sentiment": None}

    # ------------------------------------------------------------------
    # Node: assess_missing (B5) — LLM lists missing ticket details
    # ------------------------------------------------------------------

    def assess_missing(state: TicketState) -> dict[str, Any]:
        """LLM-identify important missing information in the ticket text.

        Falls back to an empty list on any error so downstream nodes always see a list.
        """
        text: str = state["text"]
        try:
            result = chat_model.complete_json(ASSESS_MISSING_SYSTEM, text)
            raw = result.get("missing_info", [])
            if not isinstance(raw, list):
                return {"missing_info": []}
            missing: list[str] = [str(item) for item in raw if isinstance(item, str)]
            return {"missing_info": missing}
        except Exception:
            _logger.exception("assess_missing node: LLM call failed; returning empty list")
            return {"missing_info": []}

    # ------------------------------------------------------------------
    # Wire edges: START → retrieve → classify → sentiment → assess_missing → END
    # ------------------------------------------------------------------

    builder: StateGraph[TicketState] = StateGraph(TicketState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("classify", classify)
    builder.add_node("sentiment", sentiment)
    builder.add_node("assess_missing", assess_missing)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "classify")
    builder.add_edge("classify", "sentiment")
    builder.add_edge("sentiment", "assess_missing")
    builder.add_edge("assess_missing", END)

    return builder.compile()


def build_default_graph() -> Any:
    """Build the graph from live settings (real Voyage + BM25 + Pinecone + Groq).

    Deferred construction (not at import) so the app boots without keys/artifact present.
    """
    from app.analyze.baseline import _BM25_ARTIFACT
    from app.providers.chat import get_chat_model
    from app.providers.embeddings import get_embedder

    return build_graph(
        embedder=get_embedder(),
        sparse_encoder=BM25SparseEncoder.load(_BM25_ARTIFACT),
        store=PineconeStore(),
        chat_model=get_chat_model(),
    )
