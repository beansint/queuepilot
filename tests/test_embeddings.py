"""A3 — GeminiEmbedder unit tests (no network).

All tests monkeypatch ``genai.Client`` so no real API call is made.
The real API is exercised by ``uv run python learn/02_embeddings.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.providers.embeddings import EMBED_DIM, GeminiEmbedder, get_embedder

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _fake_embedding(dim: int = EMBED_DIM) -> MagicMock:
    """Return a mock object whose ``.values`` is a list of floats of length ``dim``."""
    emb = MagicMock()
    emb.values = [0.1] * dim
    return emb


def _fake_response(n: int = 1, dim: int = EMBED_DIM) -> MagicMock:
    """Return a mock ``EmbedContentResponse`` with ``n`` embeddings of length ``dim``."""
    resp = MagicMock()
    resp.embeddings = [_fake_embedding(dim) for _ in range(n)]
    return resp


# ---------------------------------------------------------------------------
# embed_documents
# ---------------------------------------------------------------------------


def test_embed_documents_returns_correct_shape() -> None:
    """embed_documents returns one 768-float vector per input text."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_response(n=3)

        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_documents(["text a", "text b", "text c"])

    assert len(result) == 3
    for vec in result:
        assert len(vec) == EMBED_DIM
        assert all(isinstance(v, float) for v in vec)


def test_embed_documents_empty_input_returns_empty() -> None:
    """embed_documents([]) returns [] without touching the network."""
    with patch("app.providers.embeddings.genai"):
        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_documents([])
    assert result == []


def test_embed_documents_single_text() -> None:
    """embed_documents works for a batch of exactly one string."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_response(n=1)

        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_documents(["hello world"])

    assert len(result) == 1
    assert len(result[0]) == EMBED_DIM


def test_embed_documents_wrong_dim_raises() -> None:
    """embed_documents raises ValueError when the returned vector has the wrong length."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_response(n=1, dim=512)

        embedder = GeminiEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="512"):
            embedder.embed_documents(["test"])


# ---------------------------------------------------------------------------
# embed_query
# ---------------------------------------------------------------------------


def test_embed_query_returns_correct_shape() -> None:
    """embed_query returns a single 768-float vector."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_response(n=1)

        embedder = GeminiEmbedder(api_key="fake-key")
        result = embedder.embed_query("what is an embedding?")

    assert isinstance(result, list)
    assert len(result) == EMBED_DIM
    assert all(isinstance(v, float) for v in result)


def test_embed_query_wrong_dim_raises() -> None:
    """embed_query raises ValueError when the returned vector has the wrong length."""
    with patch("app.providers.embeddings.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.embed_content.return_value = _fake_response(n=1, dim=256)

        embedder = GeminiEmbedder(api_key="fake-key")
        with pytest.raises(ValueError, match="256"):
            embedder.embed_query("test query")


# ---------------------------------------------------------------------------
# None-values guard (SDK can return None for embeddings/values)
# ---------------------------------------------------------------------------


def test_embed_documents_none_embeddings_raises() -> None:
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


def test_embed_documents_none_values_raises() -> None:
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
# get_embedder factory
# ---------------------------------------------------------------------------


def test_get_embedder_missing_key_raises() -> None:
    """get_embedder raises RuntimeError when GEMINI_API_KEY is not set."""
    with patch("app.providers.embeddings.get_settings") as mock_settings:
        mock_settings.return_value.gemini_api_key = None
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            get_embedder()


def test_get_embedder_returns_gemini_embedder() -> None:
    """get_embedder returns a GeminiEmbedder when the key is present."""
    with (
        patch("app.providers.embeddings.get_settings") as mock_settings,
        patch("app.providers.embeddings.genai"),
    ):
        mock_settings.return_value.gemini_api_key = "test-key"
        embedder = get_embedder()
    assert isinstance(embedder, GeminiEmbedder)
