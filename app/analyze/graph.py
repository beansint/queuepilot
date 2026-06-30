"""LangGraph workflow for Slice B (scaffold).

Replaces the Slice A `Analyzer` with a `StateGraph` behind the same `/analyze` contract. State
(`TicketState`) threads through nodes; each node returns a partial-state dict that LangGraph merges.

Slice B build order (08-SLICE-B-DESIGN.md): B1 adds the scaffold + `retrieve` node; B3–B9 add
classify → sentiment → assess_missing → score → decide → draft/clarify. This module is the seam.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.providers.chat import ChatModel
from app.providers.embeddings import Embedder
from app.retrieval.hybrid import hybrid_score_norm
from app.retrieval.pinecone_store import Neighbor, PineconeStore
from app.retrieval.sparse import BM25SparseEncoder


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

    Dependencies are injected so the graph is testable with fakes (no network). ``chat_model`` is
    unused by the B1 scaffold (only ``retrieve`` exists) but is the seam the B3–B9 LLM nodes use.
    """
    effective_alpha = alpha if alpha is not None else get_settings().hybrid_alpha
    _ = chat_model  # reserved for B3+ LLM nodes

    def retrieve(state: TicketState) -> dict[str, Any]:
        """Hybrid-retrieve neighbors for the ticket text (reuses Slice A retrieval)."""
        text = state["text"]
        dense = embedder.embed_query(text)
        sparse = sparse_encoder.encode_query(text)
        weighted_dense, weighted_sparse = hybrid_score_norm(dense, sparse, effective_alpha)
        neighbors = store.hybrid_query(weighted_dense, weighted_sparse, top_k=top_k)
        return {"neighbors": neighbors}

    builder = StateGraph(TicketState)
    builder.add_node("retrieve", retrieve)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", END)
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
