"""A6 — hybrid_score_norm and to_similar_tickets unit tests (no network).

Covers:
  * hybrid_score_norm: alpha=1 leaves dense unchanged and zeroes sparse values.
  * hybrid_score_norm: alpha=0 zeroes dense and leaves sparse values unchanged.
  * hybrid_score_norm: alpha=0.5 halves both dense and sparse values.
  * hybrid_score_norm: sparse indices are never modified.
  * hybrid_score_norm: inputs are not mutated (immutability guarantee).
  * hybrid_score_norm: alpha outside [0.0, 1.0] raises ValueError.
  * to_similar_tickets: fields map correctly from Neighbor to SimilarTicket.
  * to_similar_tickets: order is preserved.
  * to_similar_tickets: empty input yields empty output.
"""

from __future__ import annotations

import pytest

from app.retrieval.hybrid import hybrid_score_norm, to_similar_tickets
from app.retrieval.pinecone_store import Neighbor
from app.retrieval.sparse import SparseVector

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

DENSE: list[float] = [0.1, 0.2, 0.3, 0.4]

SPARSE: SparseVector = {
    "indices": [10, 20, 30],
    "values": [0.5, 1.0, 2.0],
}


# ---------------------------------------------------------------------------
# hybrid_score_norm — alpha boundary values
# ---------------------------------------------------------------------------


def test_alpha_one_leaves_dense_unchanged() -> None:
    """alpha=1.0 → dense values are unchanged (multiplied by 1)."""
    weighted_dense, _ = hybrid_score_norm(DENSE, SPARSE, alpha=1.0)
    assert weighted_dense == pytest.approx([v * 1.0 for v in DENSE])


def test_alpha_one_zeroes_sparse_values() -> None:
    """alpha=1.0 → sparse values are all 0.0 (multiplied by 0)."""
    _, weighted_sparse = hybrid_score_norm(DENSE, SPARSE, alpha=1.0)
    assert weighted_sparse["values"] == pytest.approx([0.0, 0.0, 0.0])


def test_alpha_zero_zeroes_dense() -> None:
    """alpha=0.0 → dense values are all 0.0 (multiplied by 0)."""
    weighted_dense, _ = hybrid_score_norm(DENSE, SPARSE, alpha=0.0)
    assert weighted_dense == pytest.approx([0.0, 0.0, 0.0, 0.0])


def test_alpha_zero_leaves_sparse_unchanged() -> None:
    """alpha=0.0 → sparse values are unchanged (multiplied by 1)."""
    _, weighted_sparse = hybrid_score_norm(DENSE, SPARSE, alpha=0.0)
    assert weighted_sparse["values"] == pytest.approx(SPARSE["values"])


def test_alpha_half_halves_dense() -> None:
    """alpha=0.5 → dense values are halved."""
    weighted_dense, _ = hybrid_score_norm(DENSE, SPARSE, alpha=0.5)
    assert weighted_dense == pytest.approx([v * 0.5 for v in DENSE])


def test_alpha_half_halves_sparse_values() -> None:
    """alpha=0.5 → sparse values are halved."""
    _, weighted_sparse = hybrid_score_norm(DENSE, SPARSE, alpha=0.5)
    assert weighted_sparse["values"] == pytest.approx([v * 0.5 for v in SPARSE["values"]])


# ---------------------------------------------------------------------------
# hybrid_score_norm — sparse indices are always preserved
# ---------------------------------------------------------------------------


def test_sparse_indices_never_modified() -> None:
    """Sparse indices are never changed regardless of alpha."""
    for alpha in (0.0, 0.5, 1.0):
        _, weighted_sparse = hybrid_score_norm(DENSE, SPARSE, alpha=alpha)
        assert weighted_sparse["indices"] == SPARSE["indices"], (
            f"Indices changed at alpha={alpha}"
        )


# ---------------------------------------------------------------------------
# hybrid_score_norm — immutability
# ---------------------------------------------------------------------------


def test_inputs_not_mutated() -> None:
    """hybrid_score_norm must not mutate the dense list or sparse dict."""
    dense_copy = list(DENSE)
    sparse_copy: SparseVector = {
        "indices": list(SPARSE["indices"]),
        "values": list(SPARSE["values"]),
    }

    hybrid_score_norm(dense_copy, sparse_copy, alpha=0.5)

    assert dense_copy == DENSE, "dense list was mutated"
    assert sparse_copy["indices"] == SPARSE["indices"], "sparse indices were mutated"
    assert sparse_copy["values"] == SPARSE["values"], "sparse values were mutated"


# ---------------------------------------------------------------------------
# hybrid_score_norm — ValueError for invalid alpha
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_alpha", [-0.01, -1.0, 1.01, 2.0, float("inf")])
def test_out_of_range_alpha_raises_value_error(bad_alpha: float) -> None:
    """alpha outside [0.0, 1.0] raises ValueError."""
    with pytest.raises(ValueError, match="alpha"):
        hybrid_score_norm(DENSE, SPARSE, alpha=bad_alpha)


def test_alpha_exactly_zero_and_one_are_valid() -> None:
    """Boundary values 0.0 and 1.0 are valid (no exception)."""
    hybrid_score_norm(DENSE, SPARSE, alpha=0.0)
    hybrid_score_norm(DENSE, SPARSE, alpha=1.0)


# ---------------------------------------------------------------------------
# to_similar_tickets — field mapping
# ---------------------------------------------------------------------------

_NEIGHBORS: list[Neighbor] = [
    Neighbor(score=0.95, queue="billing", priority="high", type="complaint",
             snippet="I was charged twice"),
    Neighbor(score=0.80, queue=None, priority="low", type=None, snippet="Cannot login"),
    Neighbor(score=0.60, queue="tech", priority=None, type="bug", snippet="App crashes on open"),
]


def test_to_similar_tickets_maps_score() -> None:
    """score is transferred accurately."""
    tickets = to_similar_tickets(_NEIGHBORS)
    assert [t.score for t in tickets] == pytest.approx([0.95, 0.80, 0.60])


def test_to_similar_tickets_maps_queue() -> None:
    """queue (including None) is transferred correctly."""
    tickets = to_similar_tickets(_NEIGHBORS)
    assert [t.queue for t in tickets] == ["billing", None, "tech"]


def test_to_similar_tickets_maps_priority() -> None:
    """priority (including None) is transferred correctly."""
    tickets = to_similar_tickets(_NEIGHBORS)
    assert [t.priority for t in tickets] == ["high", "low", None]


def test_to_similar_tickets_maps_type() -> None:
    """type (including None) is transferred correctly."""
    tickets = to_similar_tickets(_NEIGHBORS)
    assert [t.type for t in tickets] == ["complaint", None, "bug"]


def test_to_similar_tickets_maps_snippet() -> None:
    """snippet is transferred correctly."""
    tickets = to_similar_tickets(_NEIGHBORS)
    assert [t.snippet for t in tickets] == [
        "I was charged twice",
        "Cannot login",
        "App crashes on open",
    ]


def test_to_similar_tickets_preserves_order() -> None:
    """Output order matches input order (descending score is the caller's responsibility)."""
    tickets = to_similar_tickets(_NEIGHBORS)
    assert len(tickets) == len(_NEIGHBORS)
    for ticket, neighbor in zip(tickets, _NEIGHBORS, strict=True):
        assert ticket.score == neighbor.score


def test_to_similar_tickets_empty_input() -> None:
    """Empty neighbor list returns an empty ticket list."""
    assert to_similar_tickets([]) == []
