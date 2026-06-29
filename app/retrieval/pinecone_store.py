"""Pinecone sparse-dense store for hybrid retrieval.

Creates and queries a single serverless **dotproduct** index that holds BOTH the dense (Gemini)
and sparse (BM25) vectors per record — the recommended hybrid-search layout. Alpha-weighting of the
two vectors is A6's job (`hybrid_score_norm`); this module queries with the vectors as given.

See docs/final-build-plan/02-DATA-MODEL.md (index spec + metadata) and 06-ARCHITECTURE.md.
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from pinecone import Pinecone, ServerlessSpec
from pydantic import BaseModel

from app.config import get_settings
from app.providers.embeddings import EMBED_DIM
from app.retrieval.sparse import SparseVector

#: Metadata keys we persist per record (Pinecone rejects null values, so None fields are omitted).
_METADATA_KEYS = ("queue", "priority", "type", "snippet")
_DEFAULT_NAMESPACE = "tickets"
_UPSERT_BATCH = 100
_CREATE_TIMEOUT_S = 300


class Neighbor(BaseModel):
    """One retrieved historical ticket (maps cleanly to the API's SimilarTicket)."""

    score: float
    queue: str | None = None
    priority: str | None = None
    type: str | None = None
    snippet: str = ""


class UpsertRecord(TypedDict):
    """A record to upsert: dense values + sparse vector + metadata."""

    id: str
    values: list[float]
    sparse_values: SparseVector
    metadata: dict[str, Any]


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep only known, non-None metadata keys (Pinecone metadata cannot store null)."""
    return {k: metadata[k] for k in _METADATA_KEYS if metadata.get(k) is not None}


class PineconeStore:
    """Thin wrapper over a Pinecone serverless sparse-dense index."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.pinecone_api_key:
            raise RuntimeError(
                "PINECONE_API_KEY is not set. Add it to .env (see .env.example, task A5)."
            )
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index_name = settings.pinecone_index
        self._cloud = settings.pinecone_cloud
        self._region = settings.pinecone_region
        self._index: Any = None

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------

    def ensure_index(self) -> None:
        """Create the sparse-dense index if absent, then connect. Idempotent.

        Guards against EMBED_DIM drift: the pinned model dimension
        (`providers.embeddings.EMBED_DIM`) must equal `config.embed_dim`.
        """
        configured = get_settings().embed_dim
        if EMBED_DIM != configured:
            raise RuntimeError(
                f"Embedding dimension mismatch: providers.embeddings.EMBED_DIM={EMBED_DIM} "
                f"but config.embed_dim={configured}. These must match (changing the index "
                "dimension requires a full re-index — see 02-DATA-MODEL.md)."
            )
        if not self._pc.has_index(self._index_name):
            self._pc.create_index(
                name=self._index_name,
                dimension=EMBED_DIM,
                metric="dotproduct",
                spec=ServerlessSpec(cloud=self._cloud, region=self._region),
                timeout=_CREATE_TIMEOUT_S,
            )
        self._index = self._pc.Index(self._index_name)

    def _require_index(self) -> Any:
        if self._index is None:
            self._index = self._pc.Index(self._index_name)
        return self._index

    # ------------------------------------------------------------------
    # Write / read
    # ------------------------------------------------------------------

    def upsert(
        self,
        records: list[UpsertRecord],
        namespace: str = _DEFAULT_NAMESPACE,
    ) -> int:
        """Upsert records in batches. Returns the number of vectors upserted."""
        index = self._require_index()
        total = 0
        for start in range(0, len(records), _UPSERT_BATCH):
            batch = records[start : start + _UPSERT_BATCH]
            vectors = [
                {
                    "id": rec["id"],
                    "values": rec["values"],
                    "sparse_values": {
                        "indices": rec["sparse_values"]["indices"],
                        "values": rec["sparse_values"]["values"],
                    },
                    "metadata": _clean_metadata(rec["metadata"]),
                }
                for rec in batch
            ]
            resp = index.upsert(vectors=vectors, namespace=namespace)
            total += int(getattr(resp, "upserted_count", len(vectors)) or len(vectors))
        return total

    def hybrid_query(
        self,
        dense: list[float],
        sparse: SparseVector,
        top_k: int = 5,
        namespace: str = _DEFAULT_NAMESPACE,
    ) -> list[Neighbor]:
        """Hybrid (dense + sparse) query. Returns Neighbors ordered by descending score."""
        index = self._require_index()
        result = index.query(
            namespace=namespace,
            top_k=top_k,
            vector=dense,
            sparse_vector={"indices": sparse["indices"], "values": sparse["values"]},
            include_metadata=True,
        )
        neighbors: list[Neighbor] = []
        for match in result.matches:
            meta = match.metadata or {}
            neighbors.append(
                Neighbor(
                    score=float(match.score),
                    queue=meta.get("queue"),
                    priority=meta.get("priority"),
                    type=meta.get("type"),
                    snippet=meta.get("snippet", ""),
                )
            )
        return neighbors

    def delete_namespace(self, namespace: str) -> None:
        """Delete all vectors in a namespace (used for test cleanup). Best-effort."""
        index = self._require_index()
        try:
            index.delete(delete_all=True, namespace=namespace)
        except Exception:  # noqa: BLE001 - cleanup must not mask the real assertion
            time.sleep(0.1)
