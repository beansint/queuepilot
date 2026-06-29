"""Embedding provider protocol and Gemini implementation.

Defines the ``Embedder`` protocol so retrieval code is decoupled from the embedding model.
``GeminiEmbedder`` wraps ``gemini-embedding-001`` at a fixed 768-dimensional Matryoshka output.

See docs/final-build-plan/02-DATA-MODEL.md (Pinecone index spec) and 06-ARCHITECTURE.md
(providers/ boundary).
"""

from __future__ import annotations

from typing import Protocol

from google import genai
from google.genai import types as genai_types

from app.config import get_settings

#: Fixed output dimension for ``gemini-embedding-001`` (Matryoshka, pinned at A3).
#: Changing this forces a full Pinecone re-index — see 02-DATA-MODEL.md.
EMBED_DIM: int = 768
_MODEL: str = "gemini-embedding-001"


class Embedder(Protocol):
    """Structural protocol for embedding providers.

    Callers (retrieval, ingest) depend only on this interface so the underlying
    model can be swapped without touching retrieval code.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of corpus texts using the RETRIEVAL_DOCUMENT task type."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string using the RETRIEVAL_QUERY task type."""
        ...


class GeminiEmbedder:
    """Gemini ``gemini-embedding-001`` provider at fixed ``EMBED_DIM``-dimensional output.

    Constructed once per process (via ``get_embedder()``).  The API key is accepted at
    construction time and never logged or re-exposed.
    """

    def __init__(self, api_key: str) -> None:
        self._client: genai.Client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` in a single batched call (RETRIEVAL_DOCUMENT task type).

        Returns an ordered list of 768-float vectors, one per input string.
        Raises ``ValueError`` if any returned vector has an unexpected length.
        """
        if not texts:
            return []

        resp: genai_types.EmbedContentResponse = self._client.models.embed_content(
            model=_MODEL,
            contents=texts,
            config=genai_types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=EMBED_DIM,
            ),
        )
        vectors = self._extract_vectors(resp, context="embed_documents")
        self._validate_lengths(vectors, context="embed_documents")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (RETRIEVAL_QUERY task type).

        Returns a single 768-float vector.
        Raises ``ValueError`` if the returned vector has an unexpected length.
        """
        resp: genai_types.EmbedContentResponse = self._client.models.embed_content(
            model=_MODEL,
            contents=[text],
            config=genai_types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=EMBED_DIM,
            ),
        )
        vectors = self._extract_vectors(resp, context="embed_query")
        self._validate_lengths(vectors, context="embed_query")
        return vectors[0]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_vectors(
        resp: genai_types.EmbedContentResponse,
        context: str,
    ) -> list[list[float]]:
        """Pull plain ``list[float]`` vectors out of the SDK response."""
        embeddings = resp.embeddings
        if embeddings is None:
            raise ValueError(f"{context}: response contained no embeddings")
        vectors: list[list[float]] = []
        for i, emb in enumerate(embeddings):
            if emb.values is None:
                raise ValueError(f"{context}: embedding {i} has None values")
            vectors.append(list(emb.values))
        return vectors

    @staticmethod
    def _validate_lengths(vectors: list[list[float]], context: str) -> None:
        """Raise if any vector does not have the pinned ``EMBED_DIM`` length."""
        for i, vec in enumerate(vectors):
            if len(vec) != EMBED_DIM:
                raise ValueError(
                    f"{context}: vector {i} has length {len(vec)}, expected {EMBED_DIM}. "
                    "Check output_dimensionality or model choice."
                )


def get_embedder() -> Embedder:
    """Build and return a ``GeminiEmbedder`` from the current application settings.

    Raises:
        RuntimeError: if ``GEMINI_API_KEY`` is not set in the environment / ``.env``.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Add it to .env (see .env.example, task A3)."
        )
    return GeminiEmbedder(api_key=settings.gemini_api_key)
