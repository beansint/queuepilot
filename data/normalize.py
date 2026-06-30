"""Normalize raw Kaggle CSV rows into ``TicketRecord`` instances.

Isolates the Kaggle CSV column schema so a dataset change touches exactly one file.
Pure and side-effect-free: no network calls, no file I/O beyond reading the CSV.

Column layout (``aa_dataset-tickets-multi-lang-5-2-50-version.csv``):
    subject, body, answer, type, queue, priority, language, version, tag_1..tag_8

v1 rules (see docs/final-build-plan/07-DATASET.md):
  * Keep English rows only (``language == 'en'``).
  * Drop rows whose combined text is empty after stripping.
  * Map ``subject + body → text``; keep ``queue/priority/type/answer``.
  * Assign a stable content-hash id (sha1 of subject + "\\n" + body, first 16 hex chars).

See docs/final-build-plan/02-DATA-MODEL.md (TicketRecord shape) and 06-ARCHITECTURE.md.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


class TicketRecord(BaseModel):
    """Normalized ticket record — the unit the rest of the system operates on."""

    id: str  # stable content-hash: "t_" + sha1(subject + "\n" + body)[:16]
    text: str  # subject + "\n\n" + body, stripped and blank-line-collapsed
    queue: str | None  # operational label
    priority: str | None  # high / medium / low
    type: str | None  # e.g. "Incident", "Request"
    answer: str | None  # agent answer → reply corpus (Slice B+)
    language: str  # filtered to "en" in v1


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _make_id(subject: str, body: str) -> str:
    """Return a stable ``t_``-prefixed content-hash id.

    Uses sha1 of ``subject + "\\n" + body`` encoded as UTF-8.  The first 16 hex
    characters are kept so the id is compact yet collision-resistant for ~3k records.
    Identical input always yields the same id, making re-ingests idempotent.
    """
    raw = (subject + "\n" + body).encode()
    return "t_" + hashlib.sha1(raw).hexdigest()[:16]


def _unescape(value: str) -> str:
    """Turn literal escape sequences from the CSV into real whitespace.

    The Kaggle export stores newlines as the two-character literal ``\\n`` (backslash + n),
    not actual newlines. Left as-is they pollute every embedding/BM25 vector with junk
    ``n`` tokens, so we convert them to real whitespace before embedding.
    """
    return (
        value.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\t", " ")
    )


def _clean_text(subject: str, body: str) -> str:
    """Combine subject and body, unescape literal ``\\n``, strip, collapse blank lines.

    Produces:  ``<subject>\\n\\n<body>`` with literal escape sequences converted to real
    whitespace and any run of three or more consecutive newlines collapsed to exactly two.
    """
    combined = _unescape(subject).strip() + "\n\n" + _unescape(body).strip()
    # Collapse 3+ consecutive newlines → exactly 2.
    combined = re.sub(r"\n{3,}", "\n\n", combined)
    return combined.strip()


def _or_none(value: str) -> str | None:
    """Return ``None`` for empty/whitespace strings, otherwise return stripped value."""
    stripped = value.strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_rows(csv_path: str | Path) -> Iterator[dict[str, str]]:
    """Yield rows from *csv_path* as ``dict[str, str]`` using stdlib ``csv.DictReader``.

    No external dependencies; values are always plain strings (CSV text files).

    Args:
        csv_path: Absolute or relative path to the Kaggle ticket CSV.

    Yields:
        One dict per row; keys are the CSV header columns.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Coerce explicitly: DictReader returns str values for text files;
            # the cast to str(v or "") is defensive and satisfies strict mypy.
            yield {str(k): str(v or "") for k, v in row.items()}


def normalize_rows(
    rows: Iterable[dict[str, str]],
) -> tuple[list[TicketRecord], dict[str, int]]:
    """Normalize raw CSV rows into ``TicketRecord`` instances.

    Filtering rules applied in order:
      1. Drop rows where ``language != 'en'``  (tracked as ``dropped_non_en``).
      2. Drop rows where the cleaned text is empty          (``dropped_empty``).

    Args:
        rows: Iterable of raw CSV row dicts (e.g. from ``load_rows``).

    Returns:
        A 2-tuple ``(records, stats)`` where *stats* contains integer counts
        for ``total``, ``kept``, ``dropped_non_en``, and ``dropped_empty``.
    """
    records: list[TicketRecord] = []
    stats: dict[str, int] = {
        "total": 0,
        "kept": 0,
        "dropped_non_en": 0,
        "dropped_empty": 0,
    }

    for row in rows:
        stats["total"] += 1

        language = row.get("language", "").strip()
        if language != "en":
            stats["dropped_non_en"] += 1
            continue

        subject = row.get("subject", "").strip()
        body = row.get("body", "").strip()
        text = _clean_text(subject, body)

        if not text:
            stats["dropped_empty"] += 1
            continue

        records.append(
            TicketRecord(
                id=_make_id(subject, body),
                text=text,
                queue=_or_none(row.get("queue", "")),
                priority=_or_none(row.get("priority", "")),
                type=_or_none(row.get("type", "")),
                answer=_or_none(row.get("answer", "")),
                language=language,
            )
        )
        stats["kept"] += 1

    return records, stats
