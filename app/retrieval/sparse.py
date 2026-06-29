"""BM25 sparse-vector encoder for hybrid Pinecone retrieval.

Wraps ``pinecone_text.sparse.BM25Encoder`` and normalises its output to the exact
``SparseVector`` shape that Pinecone's ``sparse_vector`` field expects:
``{"indices": list[int], "values": list[float]}``.

Usage pattern (corpus is fit once at ingest time):

    encoder = BM25SparseEncoder()
    encoder.fit(corpus_texts)
    encoder.save("data/artifacts/bm25_params.json")          # persist

    # later, at query time:
    encoder = BM25SparseEncoder.load("data/artifacts/bm25_params.json")
    sparse_vec = encoder.encode_query("VPN error 809")

See docs/final-build-plan/02-DATA-MODEL.md (BM25 fit artifact) and 06-ARCHITECTURE.md
(retrieval/ boundary).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from pinecone_text.sparse import BM25Encoder

#: Default path for persisted BM25 parameters (relative to project root).
DEFAULT_ARTIFACT_PATH: str = "data/artifacts/bm25_params.json"


class SparseVector(TypedDict):
    """Pinecone sparse-vector shape.

    Mirrors the ``sparse_vector`` field accepted by the Pinecone upsert / query API.
    Both lists are the same length; ``indices[i]`` maps to ``values[i]``.
    """

    indices: list[int]
    values: list[float]


class BM25SparseEncoder:
    """BM25 sparse encoder — fit once on the corpus, used at query time.

    Lifecycle
    ---------
    1. ``fit(corpus)``  — build vocabulary from the ingest corpus.
    2. ``save(path)``   — persist fitted params to ``data/artifacts/bm25_params.json``.
    3. ``BM25SparseEncoder.load(path)`` — restore params for query-time encoding.

    Calling ``encode_documents`` or ``encode_query`` before ``fit`` / ``load`` raises
    a ``RuntimeError`` with a clear message.
    """

    def __init__(self) -> None:
        self._encoder: BM25Encoder = BM25Encoder()
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, corpus: list[str]) -> None:
        """Fit BM25 on *corpus* and mark the encoder as ready.

        Args:
            corpus: Iterable of raw text strings (ticket subject + body).
                    Should be the same texts that will be upserted to Pinecone.
        """
        self._encoder.fit(corpus)
        self._fitted = True

    def encode_documents(self, texts: list[str]) -> list[SparseVector]:
        """Encode a batch of corpus texts as sparse vectors.

        Args:
            texts: One or more document strings (same pre-processing as ``fit``).

        Returns:
            A list of ``SparseVector`` dicts in the same order as *texts*.

        Raises:
            RuntimeError: if called before ``fit`` or ``load``.
        """
        self._require_fitted("encode_documents")
        raw = self._encoder.encode_documents(texts)
        if isinstance(raw, list):
            return [_coerce(r) for r in raw]
        # Should not happen when texts is a list, but guard for safety.
        return [_coerce(raw)]

    def encode_query(self, text: str) -> SparseVector:
        """Encode a single query string as a sparse vector.

        Args:
            text: The raw query string (e.g. the ticket text being analysed).

        Returns:
            A single ``SparseVector`` dict.

        Raises:
            RuntimeError: if called before ``fit`` or ``load``.
        """
        self._require_fitted("encode_query")
        raw = self._encoder.encode_queries(text)
        # pinecone-text returns a dict (not a list) when given a single string.
        if isinstance(raw, dict):
            return _coerce(raw)
        # Fallback for any version that returns a list regardless.
        return _coerce(raw[0])

    def save(self, path: str | Path = DEFAULT_ARTIFACT_PATH) -> None:
        """Persist fitted BM25 params to *path* (JSON).

        Parent directories are created if they do not exist.

        Raises:
            RuntimeError: if called before ``fit``.
        """
        self._require_fitted("save")
        resolved = Path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self._encoder.dump(str(resolved))

    @classmethod
    def load(cls, path: str | Path = DEFAULT_ARTIFACT_PATH) -> BM25SparseEncoder:
        """Load a previously-saved encoder from *path* (JSON).

        Returns:
            A ``BM25SparseEncoder`` that is ready to call ``encode_*`` without fitting.

        Raises:
            FileNotFoundError: if *path* does not exist.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(
                f"BM25 artifact not found at {resolved!r}. "
                "Run the ingest pipeline first (uv run python data/ingest.py)."
            )
        instance = cls()
        instance._encoder = BM25Encoder().load(str(resolved))
        instance._fitted = True
        return instance

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_fitted(self, method: str) -> None:
        """Raise ``RuntimeError`` if the encoder has not been fit or loaded."""
        if not self._fitted:
            raise RuntimeError(
                f"BM25SparseEncoder.{method}() called before the encoder is ready. "
                "Call fit(corpus) to train from scratch, or BM25SparseEncoder.load(path) "
                "to restore persisted params."
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _coerce(raw: dict[str, Any]) -> SparseVector:
    """Convert a raw ``pinecone-text`` sparse dict to our ``SparseVector`` TypedDict.

    The library already returns plain Python ``list[int]`` / ``list[float]``,
    but we coerce explicitly so the TypedDict contract is guaranteed regardless
    of library version.
    """
    return {
        "indices": [int(i) for i in raw["indices"]],
        "values": [float(v) for v in raw["values"]],
    }
