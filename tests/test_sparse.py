"""A4 — BM25SparseEncoder unit tests (no network; NLTK data downloaded on first run).

Covers:
  * encode_document and encode_query shape and types after fit.
  * RuntimeError guard when encoding before fit.
  * Round-trip persistence: fit → save → load → encode produces identical output.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.retrieval.sparse import BM25SparseEncoder, SparseVector

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

#: Small but varied corpus that gives BM25 a meaningful vocabulary to learn.
CORPUS: list[str] = [
    "VPN error code 809 cannot connect to remote server",
    "Password reset link not working in email",
    "Printer offline unable to print documents",
    "Email attachment too large to send",
    "Cannot login to account after password change",
    "Network timeout connecting to VPN endpoint",
]


def _fitted_encoder() -> BM25SparseEncoder:
    """Return a fresh encoder already fit on CORPUS."""
    enc = BM25SparseEncoder()
    enc.fit(CORPUS)
    return enc


# ---------------------------------------------------------------------------
# Shape and type checks
# ---------------------------------------------------------------------------


def test_encode_documents_returns_correct_structure() -> None:
    """encode_documents returns one SparseVector per input text, with correct keys."""
    enc = _fitted_encoder()
    results = enc.encode_documents(CORPUS[:3])

    assert len(results) == 3
    for sv in results:
        assert set(sv.keys()) == {"indices", "values"}
        assert isinstance(sv["indices"], list)
        assert isinstance(sv["values"], list)
        assert len(sv["indices"]) == len(sv["values"])


def test_encode_documents_indices_and_values_types() -> None:
    """All indices are ints and all values are floats."""
    enc = _fitted_encoder()
    sv = enc.encode_documents([CORPUS[0]])[0]

    for idx in sv["indices"]:
        assert isinstance(idx, int), f"index {idx!r} is not int"
    for val in sv["values"]:
        assert isinstance(val, float), f"value {val!r} is not float"


def test_encode_documents_in_vocab_text_has_nonzero_indices() -> None:
    """Encoding a text with known-vocabulary terms yields at least one index."""
    enc = _fitted_encoder()
    sv = enc.encode_documents(["VPN error 809"])[0]

    assert len(sv["indices"]) > 0, "Expected non-empty sparse vector for in-vocab text"


def test_encode_query_returns_single_sparse_vector() -> None:
    """encode_query returns a single SparseVector (not a list)."""
    enc = _fitted_encoder()
    sv: SparseVector = enc.encode_query("VPN error code 809")

    assert set(sv.keys()) == {"indices", "values"}
    assert isinstance(sv["indices"], list)
    assert isinstance(sv["values"], list)
    assert len(sv["indices"]) > 0


def test_encode_query_indices_and_values_types() -> None:
    """encode_query returns correctly typed indices and values."""
    enc = _fitted_encoder()
    sv = enc.encode_query("Password reset not working")

    for idx in sv["indices"]:
        assert isinstance(idx, int)
    for val in sv["values"]:
        assert isinstance(val, float)


# ---------------------------------------------------------------------------
# Guard: encode before fit
# ---------------------------------------------------------------------------


def test_encode_documents_before_fit_raises_runtime_error() -> None:
    """encode_documents raises RuntimeError if called before fit or load."""
    enc = BM25SparseEncoder()
    with pytest.raises(RuntimeError, match="fit"):
        enc.encode_documents(["anything"])


def test_encode_query_before_fit_raises_runtime_error() -> None:
    """encode_query raises RuntimeError if called before fit or load."""
    enc = BM25SparseEncoder()
    with pytest.raises(RuntimeError, match="fit"):
        enc.encode_query("anything")


def test_save_before_fit_raises_runtime_error() -> None:
    """save raises RuntimeError if called before fit."""
    enc = BM25SparseEncoder()
    with pytest.raises(RuntimeError, match="fit"):
        enc.save("/tmp/bm25_should_not_be_created.json")


# ---------------------------------------------------------------------------
# Round-trip persistence
# ---------------------------------------------------------------------------


def test_round_trip_persistence_produces_identical_output() -> None:
    """fit → save → load → encode_query returns the same sparse vector."""
    query = "VPN error code 809"
    enc_original = _fitted_encoder()
    original_sv = enc_original.encode_query(query)

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "bm25_params.json"

        # Save
        enc_original.save(artifact_path)
        assert artifact_path.exists(), "save() did not create the artifact file"

        # Load into a fresh instance
        enc_loaded = BM25SparseEncoder.load(artifact_path)
        loaded_sv = enc_loaded.encode_query(query)

    # Indices and values must match exactly
    assert original_sv["indices"] == loaded_sv["indices"], (
        "indices differ after round-trip"
    )
    assert original_sv["values"] == loaded_sv["values"], (
        "values differ after round-trip"
    )


def test_load_nonexistent_path_raises_file_not_found() -> None:
    """load() raises FileNotFoundError for a path that does not exist."""
    with pytest.raises(FileNotFoundError, match="not found"):
        BM25SparseEncoder.load("/tmp/queuepilot_nonexistent_bm25_abc123.json")


def test_save_creates_parent_directories() -> None:
    """save() creates missing parent directories automatically."""
    enc = _fitted_encoder()
    with tempfile.TemporaryDirectory() as tmpdir:
        deep_path = Path(tmpdir) / "nested" / "dir" / "bm25.json"
        enc.save(deep_path)
        assert deep_path.exists()
