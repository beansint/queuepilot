"""D8 — unit tests for snapshot cards (no network, tmp_path only)."""

from __future__ import annotations

import json
from pathlib import Path

from eval.card import build_card, write_card

_METRICS = {
    "n": 160,
    "queue_match": 0.83,
    "priority_match": 0.71,
    "type_match": 0.69,
    "label_recall_at_k": 0.90,
    "reply_quality": 0.77,
    "ece": 0.0512,
    "reliability": [
        {"lo": 0.0, "hi": 0.4, "n": 12, "claimed": 0.2, "accuracy": 0.25},
        {"lo": 0.7, "hi": 1.01, "n": 100, "claimed": 1.0, "accuracy": 0.95},
    ],
    "config": {"alpha": 0.5, "chat": "groq"},
}

_BASELINE_METRICS = {
    "n": 160,
    "queue_match": 0.75,
    "priority_match": 0.71,
    "type_match": 0.60,
    "label_recall_at_k": 0.85,
    "reply_quality": 0.70,
    "ece": 0.09,
    "reliability": [],
    "config": {"alpha": 0.3, "chat": "groq"},
}


def test_build_card_contains_key_metrics() -> None:
    card = build_card(_METRICS)
    md = card["markdown"]

    assert "83.0%" in md  # queue_match
    assert "71.0%" in md  # priority_match
    assert "90.0%" in md  # label_recall_at_k
    assert "77.0%" in md  # reply_quality
    assert "0.0512" in md  # ece
    assert "alpha=0.5" in md
    assert "Reliability table" in md
    assert card["baseline"] is None


def test_build_card_with_baseline_has_diff_column() -> None:
    card = build_card(_METRICS, baseline=_BASELINE_METRICS)
    md = card["markdown"]

    assert "Baseline" in md
    assert "Delta" in md
    # queue_match: 83.0% vs 75.0% -> +8.0pp
    assert "+8.0pp" in md
    # ece: 0.0512 - 0.09 = -0.0388
    assert "-0.0388" in md


def test_write_card_writes_json_and_markdown(tmp_path: Path) -> None:
    json_path, md_path = write_card(_METRICS, "test-prefix", snapshots_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert json_path.parent == tmp_path
    assert json_path.name == "test-prefix.json"
    assert md_path.name == "test-prefix.md"

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["n"] == 160
    assert payload["baseline"] is None

    md_content = md_path.read_text(encoding="utf-8")
    assert "QueuePilot eval snapshot" in md_content


def test_write_card_with_baseline_path(tmp_path: Path) -> None:
    baseline_json = tmp_path / "baseline.json"
    baseline_json.write_text(
        json.dumps({"metrics": _BASELINE_METRICS, "baseline": None}), encoding="utf-8"
    )

    json_path, md_path = write_card(
        _METRICS, "test-prefix-with-baseline", baseline_path=baseline_json, snapshots_dir=tmp_path
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["baseline"]["queue_match"] == 0.75

    md_content = md_path.read_text(encoding="utf-8")
    assert "+8.0pp" in md_content
