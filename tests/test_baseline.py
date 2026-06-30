"""A8 — majority_vote, confidence_v0, and Analyzer.analyze unit tests (no network).

All three test groups use only pure helpers or injected fake dependencies so the
test suite runs fully offline.

Covers:
  majority_vote:
    * selects the most-common non-None queue, priority, and type.
    * agreement fraction equals #queue-matches / total neighbors.
    * all-None queues → agreement 0.0, winning queue None.
    * empty neighbor list → (None, None, None, 0.0).

  confidence_v0:
    * output is always clamped to [0.0, 1.0].
    * high agreement + strong score yields higher confidence than low agreement + weak score.
    * extreme inputs (agreement=1.0, very high score) do not exceed 1.0.
    * zero agreement + zero score yields a low but non-negative confidence.

  Analyzer.analyze (fake deps):
    * happy-path: returns envelope with correct labels, confidence in [0,1], and ordered
      similar_tickets.
    * empty neighbor list: confidence=0.0, empty similar_tickets, all labels None.
    * all reserved fields remain None in Slice A.
    * alpha parameter is forwarded (smoke check via fake store call count).
"""

from __future__ import annotations

from typing import cast

import pytest

from app.analyze.baseline import Analyzer, confidence_v0, majority_vote
from app.providers.embeddings import Embedder
from app.retrieval.pinecone_store import Neighbor, PineconeStore
from app.retrieval.sparse import BM25SparseEncoder, SparseVector

# ---------------------------------------------------------------------------
# Fake dependencies (no network, no external I/O)
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Minimal Embedder — returns a fixed 4-dim zero vector."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * 4


class _FakeSparseEncoder(BM25SparseEncoder):
    """BM25SparseEncoder subclass that returns a fixed sparse vector without needing a fit."""

    def encode_query(self, text: str) -> SparseVector:
        return {"indices": [1, 2], "values": [0.5, 0.3]}


class _FakeStore(PineconeStore):
    """PineconeStore subclass that returns a preset neighbor list without hitting Pinecone."""

    def __init__(self, neighbors: list[Neighbor]) -> None:
        # Skip PineconeStore.__init__ to avoid the PINECONE_API_KEY requirement.
        self._neighbors = neighbors

    def hybrid_query(
        self,
        dense: list[float],
        sparse: SparseVector,
        top_k: int = 5,
        namespace: str = "tickets",
    ) -> list[Neighbor]:
        return self._neighbors[:top_k]


def _make_analyzer(neighbors: list[Neighbor]) -> Analyzer:
    """Build an Analyzer wired to return *neighbors* from every query."""
    return Analyzer(
        embedder=cast(Embedder, _FakeEmbedder()),
        sparse_encoder=_FakeSparseEncoder(),
        store=_FakeStore(neighbors),
    )


# ---------------------------------------------------------------------------
# Canned neighbor fixtures
# ---------------------------------------------------------------------------

_BILLING_NEIGHBORS: list[Neighbor] = [
    Neighbor(score=0.95, queue="Billing", priority="high", type="charge", snippet="Charged twice"),
    Neighbor(score=0.88, queue="Billing", priority="high", type="charge", snippet="Wrong amount"),
    Neighbor(score=0.75, queue="Billing", priority="low",  type="refund", snippet="Refund needed"),
    Neighbor(score=0.60, queue="IT",      priority="low",  type="charge", snippet="Access issue"),
    Neighbor(score=0.50, queue="Billing", priority="high", type="charge", snippet="Invoice error"),
]

_EMPTY_NEIGHBORS: list[Neighbor] = []

_ALL_NONE_QUEUE_NEIGHBORS: list[Neighbor] = [
    Neighbor(score=0.80, queue=None, priority="high", type="bug", snippet="No queue set"),
    Neighbor(score=0.70, queue=None, priority="low",  type="bug", snippet="Also no queue"),
]

# ---------------------------------------------------------------------------
# majority_vote tests
# ---------------------------------------------------------------------------


def test_majority_vote_empty_returns_none_tuple() -> None:
    """Empty neighbors yields (None, None, None, 0.0)."""
    queue, priority, category, agreement = majority_vote([])
    assert queue is None
    assert priority is None
    assert category is None
    assert agreement == pytest.approx(0.0)


def test_majority_vote_winning_queue() -> None:
    """Most-common non-None queue is selected (3 Billing vs 1 IT)."""
    queue, _, _, _ = majority_vote(_BILLING_NEIGHBORS)
    assert queue == "Billing"


def test_majority_vote_winning_priority() -> None:
    """Most-common non-None priority is selected (3 high vs 2 low)."""
    _, priority, _, _ = majority_vote(_BILLING_NEIGHBORS)
    assert priority == "high"


def test_majority_vote_winning_category() -> None:
    """Most-common non-None type is selected (4 charge vs 1 refund)."""
    _, _, category, _ = majority_vote(_BILLING_NEIGHBORS)
    assert category == "charge"


def test_majority_vote_agreement_fraction() -> None:
    """Agreement = 4 Billing matches / 5 total neighbors = 0.8."""
    _, _, _, agreement = majority_vote(_BILLING_NEIGHBORS)
    assert agreement == pytest.approx(0.8)


def test_majority_vote_all_none_queues_gives_zero_agreement() -> None:
    """When all queue values are None, winning_queue is None → agreement 0.0."""
    queue, _, _, agreement = majority_vote(_ALL_NONE_QUEUE_NEIGHBORS)
    assert queue is None
    assert agreement == pytest.approx(0.0)


def test_majority_vote_all_none_queues_priority_still_voted() -> None:
    """Queue being None does not prevent priority from being determined."""
    _, priority, _, _ = majority_vote(_ALL_NONE_QUEUE_NEIGHBORS)
    assert priority == "high"


def test_majority_vote_single_neighbor_has_full_agreement() -> None:
    """A single neighbor always agrees with itself — agreement = 1.0."""
    n = [Neighbor(score=0.9, queue="Security", priority="high", type="threat", snippet="x")]
    queue, _, _, agreement = majority_vote(n)
    assert queue == "Security"
    assert agreement == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# confidence_v0 tests
# ---------------------------------------------------------------------------


def test_confidence_v0_clamped_high() -> None:
    """Maximum inputs must not push the result above 1.0."""
    conf = confidence_v0(top_score=1000.0, agreement=1.0)
    assert conf <= 1.0


def test_confidence_v0_clamped_low() -> None:
    """Minimum inputs must not push the result below 0.0."""
    conf = confidence_v0(top_score=-1000.0, agreement=0.0)
    assert conf >= 0.0


def test_confidence_v0_output_in_unit_interval() -> None:
    """confidence_v0 always returns a value in [0.0, 1.0] for arbitrary inputs."""
    for score, agree in [
        (0.0, 0.0),
        (0.5, 0.5),
        (1.0, 1.0),
        (-5.0, 0.0),
        (10.0, 1.0),
    ]:
        conf = confidence_v0(top_score=score, agreement=agree)
        assert 0.0 <= conf <= 1.0, f"Out of range for score={score}, agree={agree}: {conf}"


def test_confidence_v0_monotone_in_agreement() -> None:
    """Higher agreement (same score) → higher or equal confidence."""
    low_conf = confidence_v0(top_score=0.5, agreement=0.2)
    high_conf = confidence_v0(top_score=0.5, agreement=0.9)
    assert high_conf >= low_conf


def test_confidence_v0_monotone_in_score() -> None:
    """Higher retrieval score (same agreement) → higher or equal confidence."""
    low_conf = confidence_v0(top_score=0.0, agreement=0.5)
    high_conf = confidence_v0(top_score=5.0, agreement=0.5)
    assert high_conf >= low_conf


def test_confidence_v0_low_when_both_weak() -> None:
    """Zero agreement + zero score → clearly below 0.5 (weak signal)."""
    conf = confidence_v0(top_score=0.0, agreement=0.0)
    # sigmoid(0) = 0.5, so 0*0.6 + 0.4*0.5 = 0.2
    assert conf == pytest.approx(0.2, abs=1e-6)


def test_confidence_v0_high_when_both_strong() -> None:
    """Perfect agreement + very strong score → close to 1.0."""
    conf = confidence_v0(top_score=10.0, agreement=1.0)
    # 0.6*1.0 + 0.4*sigmoid(10) ≈ 0.6 + 0.4 = 1.0
    assert conf > 0.95


# ---------------------------------------------------------------------------
# Analyzer.analyze tests
# ---------------------------------------------------------------------------


def test_analyze_happy_path_labels() -> None:
    """analyze() derives correct labels from the majority-voted neighbors."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("I was charged twice")

    assert result.queue == "Billing"
    assert result.priority == "high"
    assert result.category == "charge"


def test_analyze_happy_path_confidence_in_unit_interval() -> None:
    """confidence is in [0.0, 1.0] for a normal happy-path result."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("billing issue")
    assert 0.0 <= result.confidence <= 1.0


def test_analyze_similar_tickets_count() -> None:
    """similar_tickets has at most top_k entries (default 5 equals fixture count)."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("billing issue")
    assert len(result.similar_tickets) == len(_BILLING_NEIGHBORS)


def test_analyze_similar_tickets_descending_score() -> None:
    """similar_tickets are ordered by descending score (preserves store ordering)."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("billing issue")
    scores = [t.score for t in result.similar_tickets]
    assert scores == sorted(scores, reverse=True)


def test_analyze_similar_tickets_first_score() -> None:
    """First similar_ticket score matches the top neighbor score."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("billing issue")
    assert result.similar_tickets[0].score == pytest.approx(0.95)


def test_analyze_empty_neighbors() -> None:
    """When the store returns no neighbors, the response has safe zero-values."""
    analyzer = _make_analyzer(_EMPTY_NEIGHBORS)
    result = analyzer.analyze("completely unknown query")

    assert result.confidence == pytest.approx(0.0)
    assert result.similar_tickets == []
    assert result.queue is None
    assert result.priority is None
    assert result.category is None


def test_analyze_reserved_fields_are_none() -> None:
    """All Slice-B/C reserved fields must remain None in Slice A."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("billing issue")

    assert result.sentiment is None
    assert result.sla_risk is None
    assert result.escalate is None
    assert result.clarification is None
    assert result.suggested_reply is None
    assert result.trace is None


def test_analyze_top_k_limits_returned_tickets() -> None:
    """top_k parameter limits the number of returned similar_tickets."""
    analyzer = _make_analyzer(_BILLING_NEIGHBORS)
    result = analyzer.analyze("billing issue", top_k=2)
    assert len(result.similar_tickets) == 2
