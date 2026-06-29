"""A5 — offline unit tests for PineconeStore (no network; Pinecone client is faked)."""

from __future__ import annotations

from typing import Any

import pytest

import app.retrieval.pinecone_store as store_mod
from app.config import Settings
from app.providers.embeddings import EMBED_DIM
from app.retrieval.pinecone_store import Neighbor, PineconeStore, UpsertRecord, _clean_metadata


class FakeIndex:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.deleted: list[dict[str, Any]] = []

    def upsert(self, vectors: list[dict[str, Any]], namespace: str) -> Any:
        self.upserts.append({"vectors": vectors, "namespace": namespace})
        return type("R", (), {"upserted_count": len(vectors)})()

    def query(self, **kwargs: Any) -> Any:
        self.query_calls.append(kwargs)
        meta = {"queue": "IT", "snippet": "vpn"}
        match = type("M", (), {"id": "t1", "score": 0.9, "metadata": meta})()
        return type("Q", (), {"matches": [match]})()

    def delete(self, **kwargs: Any) -> None:
        self.deleted.append(kwargs)


class FakePinecone:
    last: FakePinecone | None = None

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.created: list[dict[str, Any]] = []
        self._has = False
        self.index = FakeIndex()
        FakePinecone.last = self

    def has_index(self, name: str) -> bool:
        return self._has

    def create_index(self, **kwargs: Any) -> None:
        self.created.append(kwargs)
        self._has = True

    def Index(self, name: str) -> FakeIndex:  # noqa: N802 - mirrors pinecone API
        return self.index


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_mod, "Pinecone", FakePinecone)
    monkeypatch.setattr(
        store_mod, "ServerlessSpec", lambda cloud, region: {"cloud": cloud, "region": region}
    )
    settings = Settings(
        pinecone_api_key="pc-test", pinecone_index="queuepilot", embed_dim=EMBED_DIM
    )
    monkeypatch.setattr(store_mod, "get_settings", lambda: settings)


def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_mod, "Pinecone", FakePinecone)
    monkeypatch.setattr(store_mod, "get_settings", lambda: Settings(pinecone_api_key=None))
    with pytest.raises(RuntimeError, match="PINECONE_API_KEY"):
        PineconeStore()


def test_ensure_index_creates_with_correct_spec(patched: None) -> None:
    store = PineconeStore()
    store.ensure_index()
    created = FakePinecone.last.created  # type: ignore[union-attr]
    assert len(created) == 1
    assert created[0]["dimension"] == EMBED_DIM
    assert created[0]["metric"] == "dotproduct"


def test_ensure_index_rejects_dim_drift(monkeypatch: pytest.MonkeyPatch, patched: None) -> None:
    monkeypatch.setattr(
        store_mod,
        "get_settings",
        lambda: Settings(pinecone_api_key="pc-test", embed_dim=EMBED_DIM + 1),
    )
    store = PineconeStore()
    with pytest.raises(RuntimeError, match="dimension mismatch"):
        store.ensure_index()


def test_upsert_shapes_payload_and_omits_none_metadata(patched: None) -> None:
    store = PineconeStore()
    store.ensure_index()
    records: list[UpsertRecord] = [
        {
            "id": "t1",
            "values": [0.1] * EMBED_DIM,
            "sparse_values": {"indices": [1, 2], "values": [0.5, 0.5]},
            "metadata": {"queue": "IT", "priority": None, "type": None, "snippet": "vpn down"},
        }
    ]
    count = store.upsert(records, namespace="tickets")
    assert count == 1
    sent = FakePinecone.last.index.upserts[0]["vectors"][0]  # type: ignore[union-attr]
    assert sent["id"] == "t1"
    assert sent["sparse_values"] == {"indices": [1, 2], "values": [0.5, 0.5]}
    # None metadata values omitted; non-None kept
    assert sent["metadata"] == {"queue": "IT", "snippet": "vpn down"}


def test_hybrid_query_maps_matches_to_neighbors(patched: None) -> None:
    store = PineconeStore()
    store.ensure_index()
    neighbors = store.hybrid_query([0.1] * EMBED_DIM, {"indices": [1], "values": [1.0]}, top_k=3)
    assert len(neighbors) == 1
    n = neighbors[0]
    assert isinstance(n, Neighbor)
    assert n.score == 0.9
    assert n.queue == "IT"
    assert n.snippet == "vpn"
    call = FakePinecone.last.index.query_calls[0]  # type: ignore[union-attr]
    assert call["top_k"] == 3
    assert "sparse_vector" in call and "vector" in call


def test_clean_metadata_filters_none_and_unknown() -> None:
    cleaned = _clean_metadata({"queue": "IT", "priority": None, "extra": "x", "snippet": "s"})
    assert cleaned == {"queue": "IT", "snippet": "s"}
