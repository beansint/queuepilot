"""D10/F2 — unit tests for ``eval.run_online`` (no network; LangSmith client mocked).

Covers:
  * ``_aggregate_human_feedback`` computes mean/count from mocked ``list_feedback`` items,
    returns ``None`` on no run ids / no feedback / a client error (never fabricates 0.0).
  * ``main()`` prints the reference-metrics honesty note and the human-feedback line, and
    still emits a snapshot card, with a mocked client end-to-end.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from eval.run_online import _aggregate_human_feedback, main

# ---------------------------------------------------------------------------
# _aggregate_human_feedback
# ---------------------------------------------------------------------------


def _feedback_item(score: Any) -> SimpleNamespace:
    return SimpleNamespace(score=score)


def test_aggregate_human_feedback_no_run_ids_returns_none() -> None:
    client = Mock()
    assert _aggregate_human_feedback(client, []) is None
    client.list_feedback.assert_not_called()


def test_aggregate_human_feedback_computes_mean_and_count() -> None:
    client = Mock()
    client.list_feedback.return_value = [
        _feedback_item(1),
        _feedback_item(0),
        _feedback_item(1),
    ]

    result = _aggregate_human_feedback(client, ["r1", "r2", "r3"])

    assert result == {"mean": pytest.approx(2 / 3), "n": 3}
    client.list_feedback.assert_called_once_with(
        run_ids=["r1", "r2", "r3"], feedback_key=["user_thumbs"]
    )


def test_aggregate_human_feedback_ignores_non_numeric_scores() -> None:
    client = Mock()
    client.list_feedback.return_value = [_feedback_item(1), _feedback_item(None)]

    result = _aggregate_human_feedback(client, ["r1"])

    assert result == {"mean": 1.0, "n": 1}


def test_aggregate_human_feedback_returns_none_when_no_feedback_found() -> None:
    client = Mock()
    client.list_feedback.return_value = []

    assert _aggregate_human_feedback(client, ["r1"]) is None


def test_aggregate_human_feedback_returns_none_on_client_error() -> None:
    client = Mock()
    client.list_feedback.side_effect = RuntimeError("network down")

    assert _aggregate_human_feedback(client, ["r1"]) is None


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def _fake_run(run_id: str, *, inputs: dict[str, Any], outputs: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(id=run_id, inputs=inputs, outputs=outputs)


def test_main_prints_note_and_human_feedback_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_client = Mock()
    fake_client.list_runs.return_value = [
        _fake_run(
            "run-1",
            inputs={"text": "printer broken"},
            outputs={"queue": "IT", "confidence": 0.8},
        ),
        _fake_run(
            "run-2",
            inputs={"text": "billing question"},
            outputs={"queue": "Billing", "confidence": 0.6},
        ),
    ]
    fake_client.list_feedback.return_value = [_feedback_item(1), _feedback_item(1)]

    monkeypatch.setattr("eval.run_online.get_langsmith_client", lambda: fake_client)

    exit_code = main(["--limit", "2"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "reference-based metrics" in out
    assert "n/a here" in out
    assert "Human feedback (user_thumbs): mean=1.000 over n=2 rated run(s) (of 2 fetched)." in out
    # Still emits the snapshot card.
    assert "QueuePilot eval snapshot" in out


def test_main_reports_no_human_feedback_when_none_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_client = Mock()
    fake_client.list_runs.return_value = [
        _fake_run(
            "run-1",
            inputs={"text": "printer broken"},
            outputs={"queue": "IT", "confidence": 0.8},
        ),
    ]
    fake_client.list_feedback.return_value = []

    monkeypatch.setattr("eval.run_online.get_langsmith_client", lambda: fake_client)

    exit_code = main([])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Human feedback (user_thumbs): n/a" in out


def test_main_returns_1_when_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("eval.run_online.get_langsmith_client", lambda: None)
    assert main([]) == 1
