"""B1 — offline test for the LangGraph scaffold (fake deps; no network)."""

from __future__ import annotations

from app.analyze.graph import build_graph
from app.providers.embeddings import EMBED_DIM
from app.retrieval.pinecone_store import Neighbor
from app.retrieval.sparse import SparseVector


class _FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBED_DIM for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBED_DIM


class _FakeEncoder:
    def encode_query(self, text: str) -> SparseVector:
        return {"indices": [1, 2], "values": [0.5, 0.5]}


class _FakeStore:
    def hybrid_query(
        self, dense: list[float], sparse: SparseVector, top_k: int = 5
    ) -> list[Neighbor]:
        return [
            Neighbor(score=0.9, queue="IT Support", priority="high", type="Incident", snippet="v"),
            Neighbor(score=0.7, queue="IT Support", priority="low", type="Incident", snippet="8"),
        ]


class _FakeChat:
    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, max_tokens: int = 512
    ) -> str:
        return "unused in B1"

    def complete_json(
        self, system: str, user: str, *, temperature: float = 0.0
    ) -> dict[str, object]:
        return {}


def test_graph_retrieve_node_populates_neighbors() -> None:
    graph = build_graph(
        _FakeEmbedder(),
        _FakeEncoder(),  # type: ignore[arg-type]
        _FakeStore(),  # type: ignore[arg-type]
        _FakeChat(),
        top_k=2,
        alpha=0.5,
    )
    result = graph.invoke({"text": "cannot connect to vpn"})
    assert "neighbors" in result
    assert len(result["neighbors"]) == 2
    assert result["neighbors"][0].queue == "IT Support"
    assert result["text"] == "cannot connect to vpn"
