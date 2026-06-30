"""B3/B5/B6 — offline tests for classify, sentiment, and assess_missing LangGraph nodes.

All tests use fake dependencies (no network, no Groq, no Pinecone). Two FakeChat variants
are provided: one returning canned success dicts, one that raises on every complete_json call.
The latter proves that each node's fallback path is triggered and returns a safe default.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.analyze.baseline import majority_vote
from app.analyze.graph import build_graph
from app.providers.embeddings import EMBED_DIM
from app.retrieval.pinecone_store import Neighbor
from app.retrieval.sparse import SparseVector

# ---------------------------------------------------------------------------
# Shared fake infrastructure (mirrors test_graph.py pattern)
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBED_DIM for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBED_DIM


class _FakeEncoder:
    def encode_query(self, text: str) -> SparseVector:
        return {"indices": [1, 2], "values": [0.5, 0.5]}


#: Fixed neighbor set reused across tests so fallback assertions are deterministic.
_NEIGHBORS: list[Neighbor] = [
    Neighbor(score=0.9, queue="IT Support", priority="high", type="Incident", snippet="test1"),
    Neighbor(score=0.7, queue="IT Support", priority="low", type="Incident", snippet="test2"),
    Neighbor(score=0.5, queue="Facilities", priority="medium", type="Request", snippet="test3"),
]


class _FakeStore:
    def hybrid_query(
        self, dense: list[float], sparse: SparseVector, top_k: int = 5
    ) -> list[Neighbor]:
        return _NEIGHBORS[:top_k]


class _FakeChatAll:
    """Returns a single dict containing all node-relevant keys.

    Each node only reads the keys it cares about (classify: category/queue/priority;
    sentiment: frustration/negativity; assess_missing: missing_info), so extra keys are harmless.
    """

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "IT Support",
            "priority": "high",
            "frustration": 0.7,
            "negativity": 0.5,
            "missing_info": ["no error code", "no account id"],
        }


class _FakeChatError:
    """Raises RuntimeError on every complete_json call — tests the fallback path of all nodes."""

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        raise RuntimeError("simulated LLM failure")


class _FakeChatClamped:
    """Returns out-of-range sentiment values — tests that sentiment node clamps to [0, 1]."""

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "IT Support",
            "priority": "high",
            "frustration": 1.8,   # above 1.0 — must be clamped to 1.0
            "negativity": -0.5,   # below 0.0 — must be clamped to 0.0
            "missing_info": [],
        }


class _FakeChatBadMissing:
    """Returns a non-list for missing_info — tests the type-guard in assess_missing."""

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return ""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0) -> dict[str, Any]:
        return {
            "category": "Incident",
            "queue": "IT Support",
            "priority": "high",
            "frustration": 0.3,
            "negativity": 0.2,
            "missing_info": "should be a list not a string",  # bad shape
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build(chat: Any) -> Any:
    """Build a compiled graph with fake deps and the given chat model."""
    return build_graph(
        _FakeEmbedder(),
        _FakeEncoder(),  # type: ignore[arg-type]
        _FakeStore(),  # type: ignore[arg-type]
        chat,
        top_k=2,
        alpha=0.5,
    )


# ---------------------------------------------------------------------------
# classify node (B3)
# ---------------------------------------------------------------------------


def test_classify_sets_category_queue_priority() -> None:
    result = _build(_FakeChatAll()).invoke({"text": "cannot connect to VPN"})
    assert result["category"] == "Incident"
    assert result["queue"] == "IT Support"
    assert result["priority"] == "high"


def test_classify_fallback_to_majority_vote_on_error() -> None:
    """When complete_json raises, classify must return majority_vote labels."""
    result = _build(_FakeChatError()).invoke({"text": "printer stopped working"})
    exp_queue, exp_priority, exp_category, _ = majority_vote(_NEIGHBORS)
    assert result["queue"] == exp_queue
    assert result["priority"] == exp_priority
    assert result["category"] == exp_category


# ---------------------------------------------------------------------------
# sentiment node (B6)
# ---------------------------------------------------------------------------


def test_sentiment_sets_floats_in_range() -> None:
    result = _build(_FakeChatAll()).invoke({"text": "I am very frustrated with this"})
    sentiment = result["sentiment"]
    assert sentiment is not None
    assert 0.0 <= sentiment["frustration"] <= 1.0
    assert 0.0 <= sentiment["negativity"] <= 1.0
    assert sentiment["frustration"] == pytest.approx(0.7)
    assert sentiment["negativity"] == pytest.approx(0.5)


def test_sentiment_clamps_out_of_range_values() -> None:
    result = _build(_FakeChatClamped()).invoke({"text": "I HATE THIS SYSTEM!!!"})
    sentiment = result["sentiment"]
    assert sentiment is not None
    assert sentiment["frustration"] == pytest.approx(1.0), "should clamp 1.8 → 1.0"
    assert sentiment["negativity"] == pytest.approx(0.0), "should clamp -0.5 → 0.0"


def test_sentiment_none_on_error() -> None:
    """When complete_json raises, sentiment must set sentiment=None (not crash)."""
    result = _build(_FakeChatError()).invoke({"text": "something is broken"})
    assert result["sentiment"] is None


# ---------------------------------------------------------------------------
# assess_missing node (B5)
# ---------------------------------------------------------------------------


def test_assess_missing_sets_list() -> None:
    result = _build(_FakeChatAll()).invoke({"text": "things are broken"})
    missing = result["missing_info"]
    assert isinstance(missing, list)
    assert "no error code" in missing
    assert "no account id" in missing


def test_assess_missing_empty_list_on_error() -> None:
    """When complete_json raises, assess_missing must return [] (not crash)."""
    result = _build(_FakeChatError()).invoke({"text": "something broken"})
    assert result["missing_info"] == []


def test_assess_missing_empty_list_on_bad_shape() -> None:
    """When missing_info is not a list, assess_missing must return [] (type guard)."""
    result = _build(_FakeChatBadMissing()).invoke({"text": "something broken"})
    assert result["missing_info"] == []


# ---------------------------------------------------------------------------
# Full graph invoke (end-to-end state shape)
# ---------------------------------------------------------------------------


def test_full_graph_invoke_populates_all_fields() -> None:
    """Full graph run must return neighbors, classification, sentiment, and missing_info."""
    text = "My laptop won't boot after the latest update. Please help ASAP."
    result = _build(_FakeChatAll()).invoke({"text": text})

    # Retrieval
    assert "neighbors" in result
    assert len(result["neighbors"]) == 2  # top_k=2

    # Classification
    assert result["category"] == "Incident"
    assert result["queue"] == "IT Support"
    assert result["priority"] == "high"

    # Sentiment
    assert result["sentiment"] is not None
    assert "frustration" in result["sentiment"]
    assert "negativity" in result["sentiment"]

    # Missing info
    assert isinstance(result["missing_info"], list)

    # Original text preserved
    assert result["text"] == text


def test_full_graph_error_path_safe_defaults() -> None:
    """Even when every LLM call fails, the graph must complete and return safe defaults."""
    result = _build(_FakeChatError()).invoke({"text": "keyboard not working"})

    # Retrieval still works (no LLM)
    assert "neighbors" in result

    # Classify falls back to majority_vote
    exp_queue, exp_priority, exp_category, _ = majority_vote(_NEIGHBORS)
    assert result["queue"] == exp_queue

    # Sentiment is None (graceful)
    assert result["sentiment"] is None

    # Missing info is empty (graceful)
    assert result["missing_info"] == []
