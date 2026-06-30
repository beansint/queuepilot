"""Embedder unit tests (no network).

Covers GeminiEmbedder, VoyageEmbedder, and the provider registry / get_embedder factory.
All SDK calls are monkeypatched so no real API traffic is made.
The live API is exercised by ``uv run python learn/02_embeddings.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.providers.embeddings import (
    EMBED_DIM,
    GeminiEmbedder,
    VoyageEmbedder,
    get_embedder,
)

# ---------------------------------------------------------------------------
# Gemini test helpers
# ---------------------------------------------------------------------------


def _fake_gemini_embedding(dim: int = GeminiEmbedder.DIM) -> MagicMock:
    """Return a mock object whose ``.values`` is a list of floats of length ``dim``."""
    emb = MagicMock()
    emb.values = [0.1] * dim
    return emb


def _fake_gemini_response(n: int = 1, dim: int = GeminiEmbedder.DIM) -> MagicMock:
    """Return a mock ``EmbedContentResponse`` with ``n`` embeddings of length ``dim``."""
    resp = MagicMock()
    resp.embeddings = [_fake_gemini_embedding(dim) for _ in range(n)]
    return resp


# ---------------------------------------------------------------------------
# GeminiEmbedder — embed_documents
# ---------------------------------------------------------------------------


def test_gemini_embed_documents_returns_correct_shape() -> None:
    """embed_documents returns one 768-float vector per input text."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_gemini_response(n=3)

        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_documents(["text a", "text b", "text c"])

    assert len(result) == 3
    for vec in result:
        assert len(vec) == GeminiEmbedder.DIM
        assert all(isinstance(v, float) for v in vec)


def test_gemini_embed_documents_empty_input_returns_empty() -> None:
    """embed_documents([]) returns [] without touching the network."""
    with patch("app.providers.embeddings.genai"):
        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_documents([])
    assert result == []


def test_gemini_embed_documents_single_text() -> None:
    """embed_documents works for a batch of exactly one string."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_gemini_response(n=1)

        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_documents(["hello world"])

    assert len(result) == 1
    assert len(result[0]) == GeminiEmbedder.DIM


def test_gemini_embed_documents_wrong_dim_raises() -> None:
    """embed_documents raises ValueError when the returned vector has the wrong length."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_gemini_response(n=1, dim=512)

        embedder = GeminiEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="512"):
            embedder.embed_documents(["test"])


# ---------------------------------------------------------------------------
# GeminiEmbedder — embed_query
# ---------------------------------------------------------------------------


def test_gemini_embed_query_returns_correct_shape() -> None:
    """embed_query returns a single 768-float vector."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_gemini_response(n=1)

        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_query("what is an embedding?")

    assert isinstance(result, list)
    assert len(result) == GeminiEmbedder.DIM
    assert all(isinstance(v, float) for v in result)


def test_gemini_embed_query_wrong_dim_raises() -> None:
    """embed_query raises ValueError when the returned vector has the wrong length."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_gemini_response(n=1, dim=256)

        embedder = GeminiEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="256"):
            embedder.embed_query("test query")


# ---------------------------------------------------------------------------
# GeminiEmbedder — None-values guard
# ---------------------------------------------------------------------------


def test_gemini_embed_documents_none_embeddings_raises() -> None:
    """embed_documents raises ValueError when the SDK response has embeddings=None."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        resp = MagicMock()
        resp.embeddings = None
        mock_client.models.embed_content.return_value = resp

        embedder = GeminiEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="no embeddings"):
            embedder.embed_documents(["test"])


def test_gemini_embed_documents_none_values_raises() -> None:
    """embed_documents raises ValueError when an individual embedding has values=None."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        emb = MagicMock()
        emb.values = None
        resp = MagicMock()
        resp.embeddings = [emb]
        mock_client.models.embed_content.return_value = resp

        embedder = GeminiEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="None values"):
            embedder.embed_documents(["test"])


# ---------------------------------------------------------------------------
# Voyage test helpers
# ---------------------------------------------------------------------------


def _fake_voyage_result(n: int = 1, dim: int = VoyageEmbedder.DIM) -> MagicMock:
    """Return a mock ``EmbeddingsObject`` with ``n`` embeddings of length ``dim``."""
    result = MagicMock()
    result.embeddings = [[0.2] * dim for _ in range(n)]
    result.total_tokens = n * 10
    return result


# ---------------------------------------------------------------------------
# VoyageEmbedder — embed_documents
# ---------------------------------------------------------------------------


def test_voyage_embed_documents_returns_correct_shape() -> None:
    """embed_documents returns one 1024-float vector per input text."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client
        mock_client.embed.return_value = _fake_voyage_result(n=3)

        embedder = VoyageEmbedder(api_key="fake-key")
        result = embedder.embed_documents(["text a", "text b", "text c"])

    assert len(result) == 3
    for vec in result:
        assert len(vec) == VoyageEmbedder.DIM
        assert all(isinstance(v, float) for v in vec)


def test_voyage_embed_documents_uses_document_input_type() -> None:
    """embed_documents passes input_type='document' to the SDK."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client
        mock_client.embed.return_value = _fake_voyage_result(n=1)

        embedder = VoyageEmbedder(api_key="fake-key")
        embedder.embed_documents(["corpus text"])

    mock_client.embed.assert_called_once()
    _, kwargs = mock_client.embed.call_args
    assert kwargs.get("input_type") == "document"


def test_voyage_embed_documents_empty_input_returns_empty() -> None:
    """embed_documents([]) returns [] without touching the SDK."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client

        embedder = VoyageEmbedder(api_key="fake-key")
        result = embedder.embed_documents([])

    assert result == []
    mock_client.embed.assert_not_called()


def test_voyage_embed_documents_wrong_dim_raises() -> None:
    """embed_documents raises ValueError when the returned vector has the wrong length."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client
        mock_client.embed.return_value = _fake_voyage_result(n=1, dim=512)

        embedder = VoyageEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="512"):
            embedder.embed_documents(["test"])


# ---------------------------------------------------------------------------
# VoyageEmbedder — embed_query
# ---------------------------------------------------------------------------


def test_voyage_embed_query_returns_correct_shape() -> None:
    """embed_query returns a single 1024-float vector."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client
        mock_client.embed.return_value = _fake_voyage_result(n=1)

        embedder = VoyageEmbedder(api_key="fake-key")
        result = embedder.embed_query("what is an embedding?")

    assert isinstance(result, list)
    assert len(result) == VoyageEmbedder.DIM
    assert all(isinstance(v, float) for v in result)


def test_voyage_embed_query_uses_query_input_type() -> None:
    """embed_query passes input_type='query' to the SDK."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client
        mock_client.embed.return_value = _fake_voyage_result(n=1)

        embedder = VoyageEmbedder(api_key="fake-key")
        embedder.embed_query("search query")

    mock_client.embed.assert_called_once()
    _, kwargs = mock_client.embed.call_args
    assert kwargs.get("input_type") == "query"


def test_voyage_embed_query_wrong_dim_raises() -> None:
    """embed_query raises ValueError when the returned vector has the wrong length."""
    with patch("app.providers.embeddings.voyageai") as mock_voyageai:
        mock_client = MagicMock()
        mock_voyageai.Client.return_value = mock_client
        mock_client.embed.return_value = _fake_voyage_result(n=1, dim=256)

        embedder = VoyageEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="256"):
            embedder.embed_query("test query")


# ---------------------------------------------------------------------------
# Provider registry / get_embedder
# ---------------------------------------------------------------------------


def test_get_embedder_voyage_returns_voyage_embedder() -> None:
    """get_embedder returns a VoyageEmbedder when provider='voyage' and key is set."""
    with (
        patch("app.providers.embeddings.get_settings") as mock_settings,
        patch("app.providers.embeddings.voyageai"),
    ):
        mock_settings.return_value.embedding_provider = "voyage"
        mock_settings.return_value.voyage_api_key = "v-test-key"
        embedder = get_embedder()
    assert isinstance(embedder, VoyageEmbedder)


def test_get_embedder_gemini_returns_gemini_embedder() -> None:
    """get_embedder returns a GeminiEmbedder when provider='gemini' and key is set."""
    with (
        patch("app.providers.embeddings.get_settings") as mock_settings,
        patch("app.providers.embeddings.genai"),
    ):
        mock_settings.return_value.embedding_provider = "gemini"
        mock_settings.return_value.gemini_api_key = "g-test-key"
        embedder = get_embedder()
    assert isinstance(embedder, GeminiEmbedder)


def test_get_embedder_unknown_provider_raises() -> None:
    """get_embedder raises RuntimeError for an unregistered provider name."""
    with patch("app.providers.embeddings.get_settings") as mock_settings:
        mock_settings.return_value.embedding_provider = "openai"
        with pytest.raises(RuntimeError, match="Unknown embedding provider"):
            get_embedder()


def test_get_embedder_missing_voyage_key_raises() -> None:
    """get_embedder raises RuntimeError when VOYAGE_API_KEY is absent."""
    with patch("app.providers.embeddings.get_settings") as mock_settings:
        mock_settings.return_value.embedding_provider = "voyage"
        mock_settings.return_value.voyage_api_key = None
        with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
            get_embedder()


def test_get_embedder_missing_gemini_key_raises() -> None:
    """get_embedder raises RuntimeError when GEMINI_API_KEY is absent."""
    with patch("app.providers.embeddings.get_settings") as mock_settings:
        mock_settings.return_value.embedding_provider = "gemini"
        mock_settings.return_value.gemini_api_key = None
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            get_embedder()


# ---------------------------------------------------------------------------
# EMBED_DIM sanity
# ---------------------------------------------------------------------------


def test_embed_dim_matches_active_provider() -> None:
    """Module-level EMBED_DIM equals VoyageEmbedder.DIM (voyage is the default provider)."""
    # This test verifies the import-time registry computation is correct.
    # It will need to be updated if the default provider changes.
    assert EMBED_DIM == VoyageEmbedder.DIM == 1024
