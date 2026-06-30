"""Baseline /analyze composition for Slice A (pure retrieval, no LLM — decision D7).

Data flow:
    text
      → embed_query (dense)  +  bm25 encode_query (sparse)
      → hybrid_score_norm(alpha)
      → PineconeStore.hybrid_query(top_k)
      → majority_vote(neighbors)   → labels + agreement
      → confidence_v0(top_score, agreement)
      → AnalyzeResponse

This module is the *only* place that composes embed + retrieve + derive.
Slice B replaces it with a LangGraph runtime behind the same /analyze contract
without changing the endpoint in main.py.

See docs/final-build-plan/06-ARCHITECTURE.md (analyze/ boundary) and
05-DECISIONS-LOCKED.md D7 (no LLM in Slice A).
"""

from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.providers.embeddings import Embedder, get_embedder
from app.retrieval.hybrid import hybrid_score_norm, to_similar_tickets
from app.retrieval.pinecone_store import Neighbor, PineconeStore
from app.retrieval.sparse import BM25SparseEncoder, SparseVector
from app.schemas import AnalyzeResponse

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: Absolute path to the BM25 fit artifact written by the ingest pipeline.
_BM25_ARTIFACT: Path = (
    Path(__file__).resolve().parent.parent.parent / "data" / "artifacts" / "bm25_params.json"
)

#: Confidence blend weights (sum to 1.0 for interpretability).
_W_AGREEMENT: float = 0.6
_W_SCORE: float = 0.4


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, no side-effects)
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    """Numerically stable logistic function — maps any real number to (0, 1).

    Uses the ``exp(-x)`` form for x ≥ 0 and the equivalent ``exp(x)/(1+exp(x))``
    form for x < 0 so that ``math.exp`` never receives a large positive argument
    (which would overflow on inputs like -1000).
    """
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _clamp01(value: float) -> float:
    """Clamp *value* to the closed interval [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def majority_vote(
    neighbors: list[Neighbor],
) -> tuple[str | None, str | None, str | None, float]:
    """Derive winning labels and queue agreement from a ranked neighbor list.

    Each label field (queue, priority, type) is decided by the most common non-None
    value among the neighbors.  ``agreement`` is the fraction of all neighbors whose
    ``queue`` equals the winning queue (0.0 if there are no neighbors or no non-None
    queue values).

    Args:
        neighbors: Retrieved neighbors in any order (order is irrelevant for voting).

    Returns:
        ``(queue, priority, category, agreement)`` where:
        - ``queue``     — most common non-None queue value, or None.
        - ``priority``  — most common non-None priority value, or None.
        - ``category``  — most common non-None *type* field value, or None.
        - ``agreement`` — fraction in [0.0, 1.0]; 0.0 when queue winner is None or no neighbors.
    """
    if not neighbors:
        return None, None, None, 0.0

    def _most_common(values: list[str | None]) -> str | None:
        non_none = [v for v in values if v is not None]
        if not non_none:
            return None
        return Counter(non_none).most_common(1)[0][0]

    queues: list[str | None] = [n.queue for n in neighbors]
    priorities: list[str | None] = [n.priority for n in neighbors]
    types: list[str | None] = [n.type for n in neighbors]

    winning_queue = _most_common(queues)
    winning_priority = _most_common(priorities)
    winning_category = _most_common(types)

    if winning_queue is None:
        agreement: float = 0.0
    else:
        agreement = sum(1 for q in queues if q == winning_queue) / len(neighbors)

    return winning_queue, winning_priority, winning_category, agreement


def confidence_v0(top_score: float, agreement: float) -> float:
    """Blended, explainable confidence score for Slice A (retrieval-only).

    Formula::

        clamp01(_W_AGREEMENT * agreement + _W_SCORE * sigmoid(top_score))

    Each component is observable and tunable:

    - ``agreement`` captures label consistency across the retrieved neighborhood.
    - ``sigmoid(top_score)`` maps the raw retrieval score to (0, 1) so it can be
      linearly blended regardless of the underlying distance metric's scale.

    This is deliberately NOT raw LLM self-confidence — it is explainable and
    dashboardable.  Later slices will add classification certainty, missing-info
    penalties, and escalation-risk adjustments.

    Args:
        top_score:  Hybrid retrieval score of the #1 neighbor.
        agreement:  Queue agreement fraction from ``majority_vote`` (in [0.0, 1.0]).

    Returns:
        Float clamped to ``[0.0, 1.0]``.
    """
    raw = _W_AGREEMENT * agreement + _W_SCORE * _sigmoid(top_score)
    return _clamp01(raw)


# ---------------------------------------------------------------------------
# Analyzer — injectable composition root
# ---------------------------------------------------------------------------


class Analyzer:
    """Compose embed + retrieve + derive into an AnalyzeResponse.

    All three dependencies are injectable so tests can supply lightweight fakes
    without touching the network.  ``Analyzer.from_settings()`` is the canonical
    production factory.

    Slice B replaces this class with a LangGraph runtime behind the same
    ``analyze(text)`` interface.
    """

    def __init__(
        self,
        embedder: Embedder,
        sparse_encoder: BM25SparseEncoder,
        store: PineconeStore,
    ) -> None:
        self._embedder: Embedder = embedder
        self._sparse_encoder: BM25SparseEncoder = sparse_encoder
        self._store: PineconeStore = store

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> Analyzer:
        """Build an Analyzer from live settings (reads .env, loads BM25 artifact).

        Intentionally NOT called at import time — deferred to the first ``/analyze``
        request so the app boots cleanly even when the BM25 artifact is absent.

        Raises:
            FileNotFoundError: if the BM25 artifact is missing (run ingest first).
            RuntimeError: if a required API key (VOYAGE_API_KEY / PINECONE_API_KEY) is absent.
        """
        embedder = get_embedder()
        sparse_encoder = BM25SparseEncoder.load(_BM25_ARTIFACT)
        store = PineconeStore()
        return cls(embedder=embedder, sparse_encoder=sparse_encoder, store=store)

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------

    def analyze(
        self,
        text: str,
        top_k: int = 5,
        alpha: float | None = None,
    ) -> AnalyzeResponse:
        """Embed + retrieve + derive labels and confidence from the ticket *text*.

        Args:
            text:   Ticket text (assumed pre-validated by ``AnalyzeRequest``).
            top_k:  Number of neighbors to retrieve (default 5).
            alpha:  Hybrid blend factor; defaults to ``settings.hybrid_alpha``.

        Returns:
            A populated Slice-A ``AnalyzeResponse``.  Reserved fields are ``None``.
        """
        effective_alpha: float = (
            alpha if alpha is not None else get_settings().hybrid_alpha
        )

        # 1. Encode query into dense + sparse vectors
        dense: list[float] = self._embedder.embed_query(text)
        sparse: SparseVector = self._sparse_encoder.encode_query(text)

        # 2. Apply hybrid weighting then query the store
        weighted_dense, weighted_sparse = hybrid_score_norm(dense, sparse, effective_alpha)
        neighbors: list[Neighbor] = self._store.hybrid_query(
            weighted_dense, weighted_sparse, top_k=top_k
        )

        # 3. Handle the empty-result edge case early
        if not neighbors:
            return AnalyzeResponse(
                category=None,
                queue=None,
                priority=None,
                confidence=0.0,
                similar_tickets=[],
            )

        # 4. Derive labels and confidence
        queue, priority, category, agreement = majority_vote(neighbors)
        conf = confidence_v0(top_score=neighbors[0].score, agreement=agreement)

        # 5. Build the envelope (all reserved fields default to None)
        return AnalyzeResponse(
            category=category,
            queue=queue,
            priority=priority,
            confidence=conf,
            similar_tickets=to_similar_tickets(neighbors),
        )


# ---------------------------------------------------------------------------
# Lazy singleton for production use
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_analyzer() -> Analyzer:
    """Return a lazily-built singleton ``Analyzer`` (constructed on first call).

    The ``lru_cache`` ensures ``Analyzer.from_settings()`` is called at most once per
    process.  If the first call raises (e.g. BM25 artifact absent), the exception
    propagates and the function is NOT cached — subsequent calls will retry.
    """
    return Analyzer.from_settings()
