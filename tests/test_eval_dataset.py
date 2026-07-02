"""D2 — unit tests for ``eval.dataset`` (no network, no real CSV file).

Covers:
  * Leakage assertion holds: sampling only ever pulls from the held-out (post-cap) pool.
  * Leakage assertion actually fires when the invariant is violated.
  * Stratified sampling returns held-out records only, respecting sample_size.
  * Edge cases from ``eval.fixtures.EDGE_CASES`` are always injected.
  * JSONL round-trip preserves example content.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from data.normalize import TicketRecord
from eval import dataset as dataset_module
from eval.dataset import EvalExample, build_eval_dataset, read_jsonl, write_jsonl
from eval.fixtures import EDGE_CASES

_COLUMNS = [
    "subject", "body", "answer", "type", "queue", "priority", "language",
    "version", "tag_1", "tag_2", "tag_3", "tag_4", "tag_5", "tag_6", "tag_7", "tag_8",
]

_QUEUES = ["Technical Support", "Billing", "General Inquiry"]
_PRIORITIES = ["high", "medium", "low"]


def _row(i: int) -> dict[str, str]:
    base: dict[str, str] = {col: "" for col in _COLUMNS}
    base["subject"] = f"Subject {i}"
    base["body"] = f"Body text describing issue number {i} in some detail."
    base["language"] = "en"
    base["queue"] = _QUEUES[i % len(_QUEUES)]
    base["priority"] = _PRIORITIES[i % len(_PRIORITIES)]
    base["type"] = "Incident"
    return base


def _write_csv(path: Path, n_rows: int) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()
        for i in range(n_rows):
            writer.writerow(_row(i))


class _FakeSettings:
    """Minimal stand-in for ``app.config.Settings`` — only ``corpus_cap`` is read."""

    def __init__(self, corpus_cap: int) -> None:
        self.corpus_cap = corpus_cap


@pytest.fixture
def small_csv(tmp_path: Path) -> Path:
    """A 50-row synthetic CSV: rows [0:30) will be 'indexed', [30:50) held out."""
    csv_path = tmp_path / "tickets.csv"
    _write_csv(csv_path, n_rows=50)
    return csv_path


def test_leakage_assertion_holds_for_normal_build(
    small_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A normal build (cap < total rows) samples strictly from the held-out pool."""
    monkeypatch.setattr(dataset_module, "get_settings", lambda: _FakeSettings(corpus_cap=30))

    examples = build_eval_dataset(csv_path=small_csv, sample_size=10, seed=13)

    from data.normalize import load_rows, normalize_rows

    records, _ = normalize_rows(load_rows(small_csv))
    indexed_ids = {r.id for r in records[:30]}

    heldout_examples = [ex for ex in examples if ex.source == "kaggle-heldout"]
    assert heldout_examples, "expected at least one held-out example"
    for ex in heldout_examples:
        assert ex.id not in indexed_ids


def test_leakage_assertion_fires_when_violated(monkeypatch: pytest.MonkeyPatch) -> None:
    """If sampling somehow draws from the indexed set, the assertion must fire loudly."""

    record = TicketRecord(
        id="t_leaked0000000000",
        text="Leaked ticket text",
        queue="Technical Support",
        priority="high",
        type="Incident",
        answer=None,
        language="en",
    )

    def _fake_normalize_rows(rows: object) -> tuple[list[TicketRecord], dict[str, int]]:
        return [record], {"total": 1, "kept": 1, "dropped_non_en": 0, "dropped_empty": 0}

    monkeypatch.setattr(dataset_module, "load_rows", lambda csv_path: iter([]))
    monkeypatch.setattr(dataset_module, "normalize_rows", _fake_normalize_rows)
    # corpus_cap=1 means records[:1] (the only record) is "indexed" AND the held-out
    # pool records[1:] is empty — force the sampler to see the record as held-out too
    # by monkeypatching _stratified_sample to (wrongly) return the indexed record.
    monkeypatch.setattr(dataset_module, "get_settings", lambda: _FakeSettings(corpus_cap=1))
    monkeypatch.setattr(dataset_module, "_stratified_sample", lambda records, **kw: [record])

    with pytest.raises(AssertionError, match="Leakage detected"):
        build_eval_dataset(csv_path="unused.csv", sample_size=5, seed=1)


def test_stratified_sample_returns_only_heldout_and_respects_size(
    small_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sampling pulls only from the held-out pool and returns <= sample_size rows."""
    monkeypatch.setattr(dataset_module, "get_settings", lambda: _FakeSettings(corpus_cap=30))

    examples = build_eval_dataset(csv_path=small_csv, sample_size=5, seed=13)
    heldout_examples = [ex for ex in examples if ex.source == "kaggle-heldout"]

    assert len(heldout_examples) <= 5
    for ex in heldout_examples:
        assert ex.outputs.get("queue") in _QUEUES
        assert ex.outputs.get("priority") in _PRIORITIES


def test_edge_cases_always_injected(small_csv: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every build includes the fixed EDGE_CASES set, tagged source='edge'."""
    monkeypatch.setattr(dataset_module, "get_settings", lambda: _FakeSettings(corpus_cap=30))

    examples = build_eval_dataset(csv_path=small_csv, sample_size=5, seed=13)
    edge_examples = [ex for ex in examples if ex.source == "edge"]

    assert len(edge_examples) == len(EDGE_CASES)
    edge_ids = {ex.id for ex in edge_examples}
    assert edge_ids == {ex.id for ex in EDGE_CASES}
    for ex in edge_examples:
        assert ex.outputs == {}


def test_jsonl_round_trip(tmp_path: Path) -> None:
    """write_jsonl -> read_jsonl reproduces the original examples exactly."""
    examples = [
        EvalExample(
            id="e1",
            inputs={"text": "hello", "metadata": {"source": "edge"}},
            outputs={},
            source="edge",
        ),
        EvalExample(
            id="e2",
            inputs={"text": "world", "metadata": {"source": "kaggle-heldout"}},
            outputs={"queue": "Billing", "priority": "low", "type": "Request"},
            source="kaggle-heldout",
        ),
    ]
    out_path = tmp_path / "out.jsonl"
    write_jsonl(examples, out_path)

    round_tripped = read_jsonl(out_path)

    assert round_tripped == examples
