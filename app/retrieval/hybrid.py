"""Hybrid-search fusion: alpha-weight dense+sparse vectors and shape retrieval results.

This module sits between vector encoding and the Pinecone query call (see 06-ARCHITECTURE.md):

    dense, sparse = hybrid_score_norm(dense_vec, sparse_vec, alpha)
    neighbors      = store.hybrid_query(dense, sparse, top_k)
    tickets        = to_similar_tickets(neighbors)

Alpha controls the dense-vs-sparse balance **before** the query. Because the Pinecone index uses
``dotproduct`` metric, the combined score is linear in the individual component scores — so scaling
the vectors scales their contribution exactly:

    weighted_dense[i]          = dense[i] * alpha
    weighted_sparse.values[i]  = sparse.values[i] * (1 - alpha)

``alpha = 1.0`` → pure dense (semantic only).
``alpha = 0.0`` → pure sparse (lexical / BM25 only).
``alpha = 0.5`` → balanced hybrid (default, ``HYBRID_ALPHA`` in config).

See docs/final-build-plan/06-ARCHITECTURE.md (data flow) and 02-DATA-MODEL.md (index spec).
"""

from __future__ import annotations

from app.retrieval.pinecone_store import Neighbor
from app.retrieval.sparse import SparseVector
from app.schemas import SimilarTicket


def hybrid_score_norm(
    dense: list[float],
    sparse: SparseVector,
    alpha: float,
) -> tuple[list[float], SparseVector]:
    """Return alpha-weighted (dense, sparse) vectors without mutating the inputs.

    Scales the dense vector by ``alpha`` and the sparse values by ``(1 - alpha)`` so
    that the Pinecone dotproduct score reflects the chosen balance between semantic
    (dense) and lexical (sparse) similarity.

    Args:
        dense:  Dense query vector (e.g. 768-dim Gemini embedding).
        sparse: Sparse BM25 query vector ``{"indices": [...], "values": [...]}``.
        alpha:  Blend factor in ``[0.0, 1.0]``.
                ``1.0`` = pure dense, ``0.0`` = pure sparse, ``0.5`` = balanced.

    Returns:
        A ``(weighted_dense, weighted_sparse)`` tuple ready to pass to
        ``PineconeStore.hybrid_query()``.

    Raises:
        ValueError: if ``alpha`` is outside ``[0.0, 1.0]``.
    """
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(
            f"alpha must be in [0.0, 1.0]; got {alpha!r}. "
            "Use alpha=1.0 for pure dense, alpha=0.0 for pure sparse."
        )

    weighted_dense: list[float] = [v * alpha for v in dense]
    weighted_sparse: SparseVector = {
        "indices": list(sparse["indices"]),  # copy — indices are unchanged
        "values": [v * (1.0 - alpha) for v in sparse["values"]],
    }
    return weighted_dense, weighted_sparse


def to_similar_tickets(neighbors: list[Neighbor]) -> list[SimilarTicket]:
    """Map retrieval-layer ``Neighbor`` objects to API-layer ``SimilarTicket`` models.

    This is the boundary crossing between the internal retrieval layer and the public
    response envelope (``AnalyzeResponse.similar_tickets``). The field names and types
    are identical (``Neighbor`` was designed to map directly — see 02-DATA-MODEL.md),
    so this is a straightforward projection.

    Args:
        neighbors: Ordered list of ``Neighbor`` objects from ``PineconeStore.hybrid_query``.
                   Ordering is preserved (callers rely on descending-score order).

    Returns:
        A list of ``SimilarTicket`` instances in the same order.
    """
    return [
        SimilarTicket(
            score=neighbor.score,
            queue=neighbor.queue,
            priority=neighbor.priority,
            type=neighbor.type,
            snippet=neighbor.snippet,
        )
        for neighbor in neighbors
    ]
