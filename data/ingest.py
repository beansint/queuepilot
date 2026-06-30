"""One-time corpus ingest: CSV → normalize → embed → sparse-encode → upsert to Pinecone.

Usage::

    uv run python data/ingest.py [--csv PATH] [--cap N] [--namespace NS]

Defaults:
    --csv        data/raw/aa_dataset-tickets-multi-lang-5-2-50-version.csv
    --cap        settings.corpus_cap  (default 3000)
    --namespace  tickets

The ingest is **idempotent**: every record's id is a stable content-hash, so
re-running with the same corpus upserts the same vectors (Pinecone deduplicates).

See docs/final-build-plan/06-ARCHITECTURE.md (ingest data flow) and 07-DATASET.md.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Standalone script: put the project root on sys.path so ``import app`` and
# ``import data`` resolve correctly when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.providers.embeddings import get_embedder  # noqa: E402
from app.retrieval.pinecone_store import PineconeStore, UpsertRecord  # noqa: E402
from app.retrieval.sparse import BM25SparseEncoder, SparseVector  # noqa: E402
from data.normalize import TicketRecord, load_rows, normalize_rows  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CSV_DEFAULT = (
    _PROJECT_ROOT / "data" / "raw" / "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
)
_BM25_ARTIFACT = _PROJECT_ROOT / "data" / "artifacts" / "bm25_params.json"
# Gemini free tier counts quota PER TEXT (~100 embeds/min), so batch size doesn't reduce
# consumption — only pacing does. Use small bursts + a proactive throttle that stays under the cap.
_EMBED_BATCH = 25  # texts per embed call (small bursts keep the sliding-window count safe)
_TARGET_RPM = 80.0  # proactive cap: stay comfortably under the free-tier ~100/min
_RATE_LIMIT_RETRIES = 8  # reactive safety net if a 429 still slips through
_DEFAULT_BACKOFF_S = 35.0  # fallback sleep when the 429 carries no explicit retry delay


def _embed_batch_with_retry(embedder: object, chunk: list[str]) -> list[list[float]]:
    """Embed one chunk, backing off and retrying on Gemini free-tier 429s.

    The free tier caps embeddings at ~100/minute, so bulk ingest must self-pace: on a
    RESOURCE_EXHAUSTED error we sleep the server-suggested ``retryDelay`` (or a default) and
    retry the same chunk, rather than failing the whole ingest.
    """
    from google.genai.errors import ClientError  # local import keeps module import light

    last_exc: Exception | None = None
    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            return embedder.embed_documents(chunk)  # type: ignore[attr-defined, no-any-return]
        except ClientError as exc:  # noqa: PERF203
            if getattr(exc, "code", None) != 429:
                raise
            last_exc = exc
            delay = _retry_delay_seconds(exc)
            print(
                f"\n  rate limited (attempt {attempt}/{_RATE_LIMIT_RETRIES}); "
                f"sleeping {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(
        f"embedding still rate-limited after {_RATE_LIMIT_RETRIES} attempts"
    ) from last_exc


def _retry_delay_seconds(exc: object) -> float:
    """Extract the server-suggested retry delay (seconds) from a 429, else the default."""
    details = getattr(exc, "details", None) or {}
    try:
        for item in details.get("error", {}).get("details", []):
            if item.get("@type", "").endswith("RetryInfo"):
                raw = str(item.get("retryDelay", "")).rstrip("s")
                return float(raw) + 1.0
    except (AttributeError, ValueError, TypeError):
        pass
    return _DEFAULT_BACKOFF_S


# ---------------------------------------------------------------------------
# Pure helpers (no network — unit-testable)
# ---------------------------------------------------------------------------


def _build_upsert_records(
    records: list[TicketRecord],
    dense_vecs: list[list[float]],
    sparse_vecs: list[SparseVector],
) -> list[UpsertRecord]:
    """Assemble ``UpsertRecord`` list from pre-computed dense and sparse vectors.

    Pure function: no network calls.  Separating this from the embedding/upsert
    steps makes the record-building logic unit-testable without hitting any API.

    Args:
        records:    Normalized ticket records (id + text + labels).
        dense_vecs: Dense Gemini embeddings, aligned 1-to-1 with *records*.
        sparse_vecs: BM25 sparse vectors, aligned 1-to-1 with *records*.

    Returns:
        One ``UpsertRecord`` per input record.
    """
    result: list[UpsertRecord] = []
    for rec, dense, sparse in zip(records, dense_vecs, sparse_vecs, strict=True):
        result.append(
            {
                "id": rec.id,
                "values": dense,
                "sparse_values": sparse,
                "metadata": {
                    "queue": rec.queue,
                    "priority": rec.priority,
                    "type": rec.type,
                    "snippet": rec.text[:200],
                },
            }
        )
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Run the full ingest pipeline."""
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Ingest Kaggle ticket CSV into the Pinecone hybrid index.",
    )
    parser.add_argument(
        "--csv",
        default=str(_CSV_DEFAULT),
        help="Path to the primary ticket CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=settings.corpus_cap,
        help="Maximum number of English records to ingest (default: %(default)s)",
    )
    parser.add_argument(
        "--namespace",
        default="tickets",
        help="Pinecone namespace to upsert into (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    cap: int = args.cap
    namespace: str = args.namespace

    # ------------------------------------------------------------------
    # Step 1: Normalize
    # ------------------------------------------------------------------
    print(f"Loading CSV: {csv_path}")
    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}\nRun: uv run python data/download.py")

    all_records, stats = normalize_rows(load_rows(csv_path))
    capped = all_records[:cap]

    print(
        f"Normalize: total={stats['total']}  kept={stats['kept']}  "
        f"dropped_non_en={stats['dropped_non_en']}  dropped_empty={stats['dropped_empty']}"
    )
    print(f"Capping corpus to {len(capped)} records (cap={cap})")

    if not capped:
        print("No records after filtering. Exiting.")
        return

    texts = [r.text for r in capped]

    # ------------------------------------------------------------------
    # Step 2: Fit BM25 and persist artifact
    # ------------------------------------------------------------------
    print("Fitting BM25 sparse encoder ...")
    encoder = BM25SparseEncoder()
    encoder.fit(texts)
    encoder.save(_BM25_ARTIFACT)
    print(f"BM25 artifact saved → {_BM25_ARTIFACT}")

    # ------------------------------------------------------------------
    # Step 3: Connect to Pinecone BEFORE the loop so we upsert incrementally.
    # ------------------------------------------------------------------
    print("Connecting to Pinecone ...")
    embedder = get_embedder()
    store = PineconeStore()
    store.ensure_index()

    # ------------------------------------------------------------------
    # Step 4: Stream — embed + sparse-encode + upsert EACH batch immediately.
    # Incremental upserts make the ingest durable (a crash keeps everything
    # already written) and observable (Pinecone fills gradually), instead of
    # buffering all vectors in memory and writing once at the very end.
    # ------------------------------------------------------------------
    total = len(capped)
    print(f"Streaming {total} records → namespace='{namespace}' (batch={_EMBED_BATCH}) ...")
    embedded = 0
    upserted = 0
    # seconds/batch needed to hold the target embeds-per-minute rate
    throttle_s = _EMBED_BATCH / _TARGET_RPM * 60.0
    for start in range(0, total, _EMBED_BATCH):
        batch = capped[start : start + _EMBED_BATCH]
        batch_texts = [r.text for r in batch]
        t0 = time.monotonic()
        dense = _embed_batch_with_retry(embedder, batch_texts)
        sparse = encoder.encode_documents(batch_texts)
        records = _build_upsert_records(batch, dense, sparse)
        upserted += store.upsert(records, namespace=namespace)
        embedded += len(batch)
        print(f"  {embedded}/{total} embedded + upserted", flush=True)
        # Proactively pace to stay under the free-tier limit (skip the wait on the final batch).
        if embedded < total:
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, throttle_s - elapsed))

    # ------------------------------------------------------------------
    # Step 7: Honest summary
    # ------------------------------------------------------------------
    print()
    print("=== Ingest Summary ===")
    print(f"  csv:            {csv_path.name}")
    print(f"  namespace:      {namespace}")
    print(f"  total rows:     {stats['total']}")
    print(f"  kept (en):      {stats['kept']}")
    print(f"  dropped non-en: {stats['dropped_non_en']}")
    print(f"  dropped empty:  {stats['dropped_empty']}")
    print(f"  capped at:      {cap}")
    print(f"  embedded:       {embedded}")
    print(f"  upserted:       {upserted}")
    print("======================")


if __name__ == "__main__":
    main()
