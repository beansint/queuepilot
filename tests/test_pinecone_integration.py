"""A5 — LIVE integration test: real Gemini + BM25 + Pinecone end-to-end hybrid retrieval.

Skipped by default. Run explicitly with:

    QUEUEPILOT_RUN_INTEGRATION=1 uv run pytest -m integration

It creates the real index (if absent), upserts ~20 fixtures into the `test-a5` namespace, asserts a
VPN query retrieves a VPN ticket, then deletes the namespace (the index is kept for A7).
"""

from __future__ import annotations

import os

import pytest

from app.providers.embeddings import get_embedder
from app.retrieval.pinecone_store import PineconeStore, UpsertRecord
from app.retrieval.sparse import BM25SparseEncoder

pytestmark = pytest.mark.integration

_RUN = os.environ.get("QUEUEPILOT_RUN_INTEGRATION") == "1"

_FIXTURES: list[tuple[str, str, str]] = [
    ("vpn-1", "IT Support", "Cannot connect to the company VPN from home, it times out."),
    ("vpn-2", "IT Support", "VPN client shows error 809 and will not establish a tunnel."),
    ("print-1", "IT Support", "Office printer on floor 3 is jammed and offline."),
    ("print-2", "IT Support", "Printer driver missing after the latest Windows update."),
    ("pw-1", "Identity", "I forgot my password and cannot log into my account."),
    ("pw-2", "Identity", "Account is locked after too many failed login attempts."),
    ("bill-1", "Billing", "I was charged twice for my subscription this month."),
    ("bill-2", "Billing", "Need a refund for an accidental annual plan purchase."),
    ("mail-1", "IT Support", "Outlook keeps asking for my password and won't sync email."),
    ("mail-2", "IT Support", "Emails are stuck in the outbox and not sending."),
    ("net-1", "IT Support", "Wi-Fi in the east wing keeps dropping every few minutes."),
    ("net-2", "IT Support", "Ethernet port at my desk has no network connectivity."),
    ("hw-1", "IT Support", "Laptop battery drains within an hour of unplugging."),
    ("hw-2", "IT Support", "External monitor is not detected over USB-C."),
    ("sw-1", "IT Support", "Excel crashes whenever I open a large spreadsheet."),
    ("sw-2", "IT Support", "Slack will not launch after the latest update."),
    ("acc-1", "Identity", "Please grant me access to the shared finance drive."),
    ("acc-2", "Identity", "New hire needs an email account and badge provisioned."),
    ("sec-1", "Security", "I received a suspicious phishing email asking for credentials."),
    ("sec-2", "Security", "My antivirus flagged a file I downloaded from a vendor."),
]


@pytest.mark.skipif(not _RUN, reason="set QUEUEPILOT_RUN_INTEGRATION=1 to run live Pinecone test")
def test_hybrid_retrieval_end_to_end() -> None:
    namespace = "test-a5"
    texts = [t for _, _, t in _FIXTURES]

    embedder = get_embedder()
    bm25 = BM25SparseEncoder()
    bm25.fit(texts)

    dense = embedder.embed_documents(texts)
    sparse = bm25.encode_documents(texts)
    records: list[UpsertRecord] = [
        {
            "id": tid,
            "values": dense[i],
            "sparse_values": sparse[i],
            "metadata": {"queue": queue, "snippet": text[:200]},
        }
        for i, (tid, queue, text) in enumerate(_FIXTURES)
    ]

    store = PineconeStore()
    store.ensure_index()
    try:
        upserted = store.upsert(records, namespace=namespace)
        assert upserted == len(_FIXTURES)

        # Give the (eventually-consistent) index a moment to index the upserts.
        import time

        query = "cannot connect to vpn from home"
        q_dense = embedder.embed_query(query)
        q_sparse = bm25.encode_query(query)

        top_ids: list[str] = []
        for _ in range(10):
            neighbors = store.hybrid_query(q_dense, q_sparse, top_k=5, namespace=namespace)
            top_ids = [n.snippet for n in neighbors]
            if any("vpn" in n.snippet.lower() for n in neighbors):
                break
            time.sleep(2)

        assert any("vpn" in s.lower() for s in top_ids), (
            f"expected a VPN ticket in top-k, got {top_ids}"
        )
    finally:
        store.delete_namespace(namespace)
