"""A7 — unit tests for ``data.normalize`` (no network, no live APIs).

Covers:
  * Language filter: ``de`` rows are dropped, ``en`` rows are kept.
  * Empty-text filter: rows with empty subject + body are dropped.
  * Text format: ``text`` field is ``subject + "\\n\\n" + body``.
  * Id determinism: same subject + body → same id on every call.
  * Id prefix: every id starts with ``t_`` and is exactly 18 chars.
  * Stats counts: ``total``, ``kept``, ``dropped_non_en``, ``dropped_empty`` are correct.
"""

from __future__ import annotations

import csv
from pathlib import Path

from data.normalize import load_rows, normalize_rows

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: All columns present in the primary Kaggle CSV.
_COLUMNS = [
    "subject", "body", "answer", "type", "queue", "priority", "language",
    "version", "tag_1", "tag_2", "tag_3", "tag_4", "tag_5", "tag_6", "tag_7", "tag_8",
]


def _row(
    subject: str = "Default Subject",
    body: str = "Default body text",
    language: str = "en",
    **kwargs: str,
) -> dict[str, str]:
    """Build a minimal CSV-row dict with sensible defaults for unused columns."""
    base: dict[str, str] = {col: "" for col in _COLUMNS}
    base["subject"] = subject
    base["body"] = body
    base["language"] = language
    base.update(kwargs)
    return base


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write *rows* to a CSV file at *path* using stdlib csv.DictWriter."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Language filter
# ---------------------------------------------------------------------------


def test_language_filter_drops_de(tmp_path: Path) -> None:
    """Rows with ``language='de'`` are dropped; ``en`` rows are kept."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="English ticket", body="help me", language="en"),
        _row(subject="German ticket", body="hilf mir", language="de"),
    ])
    records, stats = normalize_rows(load_rows(csv_file))
    assert stats["dropped_non_en"] == 1
    assert stats["kept"] == 1
    assert len(records) == 1
    assert records[0].language == "en"


def test_language_filter_other_lang_is_also_dropped(tmp_path: Path) -> None:
    """Non-'en' languages beyond 'de' (e.g. 'fr') are also dropped."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="French ticket", body="aide moi", language="fr"),
        _row(subject="English ticket", body="help me", language="en"),
    ])
    records, stats = normalize_rows(load_rows(csv_file))
    assert stats["dropped_non_en"] == 1
    assert stats["kept"] == 1


# ---------------------------------------------------------------------------
# Empty-text filter
# ---------------------------------------------------------------------------


def test_empty_body_and_subject_dropped(tmp_path: Path) -> None:
    """Rows where both subject and body are empty/whitespace are dropped."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="Good ticket", body="please fix", language="en"),
        _row(subject="", body="", language="en"),
        _row(subject="   ", body="   ", language="en"),
    ])
    records, stats = normalize_rows(load_rows(csv_file))
    assert stats["dropped_empty"] == 2
    assert stats["kept"] == 1


def test_non_empty_subject_with_empty_body_is_kept(tmp_path: Path) -> None:
    """A ticket with only a subject (no body) is kept — text is not empty."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="Subject only", body="", language="en"),
    ])
    records, stats = normalize_rows(load_rows(csv_file))
    assert stats["kept"] == 1
    assert records[0].text.startswith("Subject only")


# ---------------------------------------------------------------------------
# Text format
# ---------------------------------------------------------------------------


def test_text_is_subject_double_newline_body(tmp_path: Path) -> None:
    """``text`` field is ``subject + '\\n\\n' + body``."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="My Subject", body="My body here", language="en"),
    ])
    records, _ = normalize_rows(load_rows(csv_file))
    assert records[0].text == "My Subject\n\nMy body here"


def test_text_strips_surrounding_whitespace(tmp_path: Path) -> None:
    """Leading/trailing whitespace in subject and body is stripped."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="  Subject  ", body="  body  ", language="en"),
    ])
    records, _ = normalize_rows(load_rows(csv_file))
    assert records[0].text == "Subject\n\nbody"


def test_literal_escape_sequences_are_unescaped(tmp_path: Path) -> None:
    """The Kaggle export stores literal ``\\n`` (backslash+n) — these must become real
    whitespace, never survive into the embedded text."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="Hi", body="Line one.\\n\\nLine two.\\tTabbed.", language="en"),
    ])
    records, _ = normalize_rows(load_rows(csv_file))
    text = records[0].text
    assert "\\n" not in text, f"literal backslash-n survived: {text!r}"
    assert "\\t" not in text, f"literal backslash-t survived: {text!r}"
    assert "Line one." in text and "Line two." in text and "Tabbed." in text


# ---------------------------------------------------------------------------
# Id determinism and format
# ---------------------------------------------------------------------------


def test_id_is_deterministic(tmp_path: Path) -> None:
    """Same subject + body always produces the same id."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="Stable Subject", body="Stable body", language="en"),
    ])
    # Load and normalize twice independently.
    records_a, _ = normalize_rows(load_rows(csv_file))
    records_b, _ = normalize_rows(load_rows(csv_file))
    assert records_a[0].id == records_b[0].id


def test_id_format(tmp_path: Path) -> None:
    """Id starts with 't_' and is exactly 18 characters (prefix + 16 hex)."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="Hello", body="World", language="en"),
    ])
    records, _ = normalize_rows(load_rows(csv_file))
    ticket_id = records[0].id
    assert ticket_id.startswith("t_"), f"id {ticket_id!r} does not start with 't_'"
    assert len(ticket_id) == 18, f"id {ticket_id!r} has length {len(ticket_id)}, expected 18"
    assert all(c in "0123456789abcdef" for c in ticket_id[2:]), (
        f"id suffix {ticket_id[2:]!r} is not lowercase hex"
    )


def test_different_inputs_produce_different_ids(tmp_path: Path) -> None:
    """Different subject/body combinations produce different ids."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="Ticket A", body="body A", language="en"),
        _row(subject="Ticket B", body="body B", language="en"),
    ])
    records, _ = normalize_rows(load_rows(csv_file))
    assert records[0].id != records[1].id


# ---------------------------------------------------------------------------
# Stats counts
# ---------------------------------------------------------------------------


def test_stats_counts_all_categories(tmp_path: Path) -> None:
    """Stats dict counts match actual filtering decisions."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="A", body="alpha", language="en"),   # kept
        _row(subject="B", body="beta", language="de"),    # dropped_non_en
        _row(subject="C", body="gamma", language="en"),   # kept
        _row(subject="", body="", language="en"),          # dropped_empty
    ])
    records, stats = normalize_rows(load_rows(csv_file))
    assert stats["total"] == 4
    assert stats["kept"] == 2
    assert stats["dropped_non_en"] == 1
    assert stats["dropped_empty"] == 1
    assert len(records) == 2


def test_stats_all_dropped_non_en(tmp_path: Path) -> None:
    """All-German CSV results in zero kept records."""
    csv_file = tmp_path / "tickets.csv"
    _write_csv(csv_file, [
        _row(subject="A", body="text", language="de"),
        _row(subject="B", body="text", language="de"),
    ])
    records, stats = normalize_rows(load_rows(csv_file))
    assert stats["total"] == 2
    assert stats["kept"] == 0
    assert stats["dropped_non_en"] == 2
    assert stats["dropped_empty"] == 0
    assert records == []
