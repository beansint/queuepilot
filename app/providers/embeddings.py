"""Embedding provider protocol, Gemini / Voyage implementations, and provider registry.

Defines the ``Embedder`` protocol so retrieval code is decoupled from the embedding model.
``GeminiEmbedder`` wraps ``gemini-embedding-001`` (768 dims).
``VoyageEmbedder`` wraps ``voyage-3.5-lite`` (1024 dims) and is the default provider.

The active provider is controlled by ``settings.embedding_provider``; ``EMBED_DIM`` resolves to
that provider's fixed dimension so ``pinecone_store.ensure_index`` stays correct after a swap.

See docs/final-build-plan/02-DATA-MODEL.md (Pinecone index spec), 05-DECISIONS-LOCKED.md D11,
and 06-ARCHITECTURE.md (providers/ boundary).
"""

from __future__ import annotations

from typing import Any, Protocol

import voyageai
from google import genai
from google.genai import types as genai_types

from app.config import get_settings

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GeminiEmbedder
# ---------------------------------------------------------------------------


class GeminiEmbedder:
    """Gemini ``gemini-embedding-001`` provider at fixed 768-dimensional output.

    Constructed once per process (via ``get_embedder()``).  The API key is accepted at
    construction time and never logged or re-exposed.
    """

    DIM: int = 768
    MODEL: str = "gemini-embedding-001"

    def __init__(self, api_key: str) -> None:
        self._client: genai.Client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` in a single batched call (RETRIEVAL_DOCUMENT task type).

        Returns an ordered list of ``DIM``-float vectors, one per input string.
        Raises ``ValueError`` if any returned vector has an unexpected length.
        """
        if not texts:
            return []

        resp: genai_types.EmbedContentResponse = self._client.models.embed_content(
            model=self.MODEL,
            contents=texts,  # type: ignore[arg-type]  # SDK accepts list[str] at runtime
            config=genai_types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.DIM,
            ),
        )
        vectors = self._extract_vectors(resp, context="embed_documents")
        self._validate_lengths(vectors, context="embed_documents")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (RETRIEVAL_QUERY task type).

        Returns a single ``DIM``-float vector.
        Raises ``ValueError`` if the returned vector has an unexpected length.
        """
        resp: genai_types.EmbedContentResponse = self._client.models.embed_content(
            model=self.MODEL,
            contents=[text],  # type: ignore[arg-type]  # SDK accepts list[str] at runtime
            config=genai_types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.DIM,
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

    def _validate_lengths(self, vectors: list[list[float]], context: str) -> None:
        """Raise if any vector does not have the class-pinned ``DIM`` length."""
        for i, vec in enumerate(vectors):
            if len(vec) != self.DIM:
                raise ValueError(
                    f"{context}: vector {i} has length {len(vec)}, expected {self.DIM}. "
                    "Check output_dimensionality or model choice."
                )


# ---------------------------------------------------------------------------
# VoyageEmbedder
# ---------------------------------------------------------------------------


class VoyageEmbedder:
    """Voyage ``voyage-3.5-lite`` provider at fixed 1024-dimensional output.

    ``voyageai.Client`` handles 429 rate-limit back-off internally (``max_retries=5``),
    so this class needs no custom retry logic.  The API key is never logged or re-exposed.
    """

    DIM: int = 1024
    MODEL: str = "voyage-3.5-lite"

    def __init__(self, api_key: str) -> None:
        # voyageai has no type stubs; client is typed Any (see pyproject.toml overrides)
        self._client: Any = voyageai.Client(  # type: ignore[attr-defined]
            api_key=api_key, max_retries=5
        )

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` as corpus documents (``input_type="document"``).

        Returns an ordered list of 1024-float vectors, one per input string.
        Raises ``ValueError`` if any returned vector has an unexpected length.
        """
        if not texts:
            return []

        result = self._client.embed(texts, model=self.MODEL, input_type="document")
        vectors: list[list[float]] = [list(v) for v in result.embeddings]
        self._validate_lengths(vectors, context="embed_documents")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (``input_type="query"``).

        Returns a single 1024-float vector.
        Raises ``ValueError`` if the returned vector has an unexpected length.
        """
        result = self._client.embed([text], model=self.MODEL, input_type="query")
        vectors: list[list[float]] = [list(v) for v in result.embeddings]
        self._validate_lengths(vectors, context="embed_query")
        return vectors[0]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_lengths(self, vectors: list[list[float]], context: str) -> None:
        """Raise if any vector does not have the class-pinned ``DIM`` length."""
        for i, vec in enumerate(vectors):
            if len(vec) != self.DIM:
                raise ValueError(
                    f"{context}: vector {i} has length {len(vec)}, expected {self.DIM}. "
                    "Check model or output_dimension setting."
                )


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

#: Provider registry: maps provider name → embedder class.
#: Both classes share the same ``__init__(self, api_key: str)`` signature so
#: ``get_embedder`` can construct either without special-casing the call site.
_PROVIDERS: dict[str, type[GeminiEmbedder] | type[VoyageEmbedder]] = {
    "voyage": VoyageEmbedder,
    "gemini": GeminiEmbedder,
}

#: Mapping from provider name → the settings attribute holding that provider's key.
_PROVIDER_KEY_ATTRS: dict[str, str] = {
    "voyage": "voyage_api_key",
    "gemini": "gemini_api_key",
}

#: Active provider's fixed output dimension.  Imported by ``pinecone_store.ensure_index``
#: to assert it equals ``config.embed_dim``.  Changing ``EMBEDDING_PROVIDER`` in .env
#: requires a full Pinecone re-index — see 02-DATA-MODEL.md and D11.
EMBED_DIM: int = _PROVIDERS[get_settings().embedding_provider].DIM


def get_embedder() -> Embedder:
    """Build and return the configured embedder from the provider registry.

    Reads ``settings.embedding_provider`` to select the class, constructs it with the
    matching API key from settings, and returns it as an ``Embedder``.

    Raises:
        RuntimeError: if the provider name is unknown or the required API key is absent.
    """
    settings = get_settings()
    provider = settings.embedding_provider

    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise RuntimeError(
            f"Unknown embedding provider {provider!r}. "
            f"Valid providers: {sorted(_PROVIDERS)}. "
            "Check EMBEDDING_PROVIDER in .env."
        )

    key_attr = _PROVIDER_KEY_ATTRS[provider]
    api_key: str | None = getattr(settings, key_attr)
    if not api_key:
        env_var = key_attr.upper()
        raise RuntimeError(
            f"{env_var} is not set. "
            f"Add it to .env (see .env.example) to use the '{provider}' provider."
        )

    return cls(api_key=api_key)
