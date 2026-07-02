"""Eval snapshot cards: aggregate metrics → JSON + Markdown (D8).

Pure and offline-testable: ``build_card`` takes a plain ``metrics`` dict (already
aggregated by the caller — ``run_experiment.py`` or ``run_online.py``) and returns a
JSON-serializable card dict plus a rendered Markdown string. ``write_card`` is the only
function that touches the filesystem.

Expected ``metrics`` shape (all keys optional; absent keys are rendered as "n/a" /
skipped so a partial run is never rounded up to a full score — see 11-SLICE-D-DESIGN.md
"Honest metrics"):

    {
        "n": 160,
        "queue_match": 0.83,
        "priority_match": 0.71,
        "type_match": 0.69,
        "label_recall_at_k": 0.90,
        "reply_quality": 0.77,
        "ece": 0.05,
        "reliability": [{"lo": 0.0, "hi": 0.4, "n": 12, "claimed": 0.2, "accuracy": 0.25}, ...],
        "config": {"alpha": 0.5, "chat": "groq", "judge_model": "gemini-2.5-flash"},
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Per-example score metrics rendered as percentages in the card body.
_PERCENT_METRICS: list[tuple[str, str]] = [
    ("queue_match", "Queue exact-match"),
    ("priority_match", "Priority exact-match"),
    ("type_match", "Type exact-match"),
    ("label_recall_at_k", "Label-recall@k"),
    ("reply_quality", "Judge mean (reply quality)"),
]


def _fmt_pct(value: float | None) -> str:
    """Format a ``[0, 1]`` metric as a percentage string, or ``"n/a"`` when absent."""
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _fmt_delta_pct(current: float | None, baseline: float | None) -> str:
    """Format a percentage-point delta between two ``[0, 1]`` metrics."""
    if current is None or baseline is None:
        return "n/a"
    delta = (current - baseline) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}pp"


def build_card(
    metrics: dict[str, Any], *, baseline: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a snapshot card dict (JSON payload + rendered Markdown) from aggregate ``metrics``.

    Args:
        metrics: Aggregate metrics for this experiment/run (see module docstring for shape).
        baseline: Optional metrics dict from a prior card, for a side-by-side diff column.

    Returns:
        ``{"metrics": metrics, "baseline": baseline, "markdown": <str>}``.
    """
    markdown = _render_markdown(metrics, baseline)
    return {"metrics": metrics, "baseline": baseline, "markdown": markdown}


def _render_markdown(metrics: dict[str, Any], baseline: dict[str, Any] | None) -> str:
    """Render the human-readable Markdown card."""
    lines: list[str] = []
    n = metrics.get("n")
    lines.append("# QueuePilot eval snapshot")
    lines.append("")
    lines.append(f"- **N examples**: {n if n is not None else 'n/a'}")

    config = metrics.get("config") or {}
    if config:
        config_str = ", ".join(f"{k}={v}" for k, v in config.items())
        lines.append(f"- **Config**: {config_str}")
    lines.append("")

    has_baseline = baseline is not None
    header = "| Metric | Score |"
    sep = "|---|---|"
    if has_baseline:
        header = "| Metric | Score | Baseline | Delta |"
        sep = "|---|---|---|---|"
    lines.append(header)
    lines.append(sep)

    for key, label in _PERCENT_METRICS:
        current = metrics.get(key)
        row = f"| {label} | {_fmt_pct(current)} |"
        if has_baseline:
            base_value = (baseline or {}).get(key)
            row = (
                f"| {label} | {_fmt_pct(current)} | {_fmt_pct(base_value)} | "
                f"{_fmt_delta_pct(current, base_value)} |"
            )
        lines.append(row)

    ece = metrics.get("ece")
    ece_str = f"{ece:.4f}" if isinstance(ece, int | float) else "n/a"
    row = f"| Expected Calibration Error (ECE) | {ece_str} |"
    if has_baseline:
        base_ece = (baseline or {}).get("ece")
        base_ece_str = f"{base_ece:.4f}" if isinstance(base_ece, int | float) else "n/a"
        if isinstance(ece, int | float) and isinstance(base_ece, int | float):
            delta = ece - base_ece
            delta_str = f"{'+' if delta >= 0 else ''}{delta:.4f}"
        else:
            delta_str = "n/a"
        row = f"| Expected Calibration Error (ECE) | {ece_str} | {base_ece_str} | {delta_str} |"
    lines.append(row)

    reliability = metrics.get("reliability") or []
    if reliability:
        lines.append("")
        lines.append("## Reliability table")
        lines.append("")
        lines.append("| Bucket | N | Claimed | Accuracy |")
        lines.append("|---|---|---|---|")
        for row_data in reliability:
            lo = row_data.get("lo")
            hi = row_data.get("hi")
            bucket_n = row_data.get("n")
            claimed = row_data.get("claimed")
            accuracy = row_data.get("accuracy")
            lines.append(
                f"| [{lo}, {hi}) | {bucket_n} | {_fmt_pct(claimed)} | {_fmt_pct(accuracy)} |"
            )

    skipped = metrics.get("skipped_evaluators")
    if skipped:
        lines.append("")
        lines.append(f"- **Skipped evaluators**: {', '.join(skipped)}")

    lines.append("")
    return "\n".join(lines)


#: Default output directory for snapshot cards; overridable in tests via ``snapshots_dir``.
DEFAULT_SNAPSHOTS_DIR = Path(__file__).resolve().parent / "snapshots"


def write_card(
    metrics: dict[str, Any],
    prefix: str,
    *,
    baseline_path: str | Path | None = None,
    snapshots_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Build a card and write it to ``<snapshots_dir>/<prefix>.json`` / ``.md``.

    Args:
        metrics: Aggregate metrics for this experiment/run.
        prefix: Experiment prefix (used as the filename stem), e.g. ``"a0.5-groq"``.
        baseline_path: Optional path to a previously written ``<prefix>.json`` card to
            diff against.
        snapshots_dir: Output directory. Defaults to ``eval/snapshots/``; tests pass
            ``tmp_path`` to avoid touching the repo's committed snapshots.

    Returns:
        ``(json_path, markdown_path)``.
    """
    baseline: dict[str, Any] | None = None
    if baseline_path is not None:
        baseline_file = Path(baseline_path)
        if baseline_file.exists():
            baseline_payload = json.loads(baseline_file.read_text(encoding="utf-8"))
            baseline = baseline_payload.get("metrics")

    card = build_card(metrics, baseline=baseline)

    resolved_dir = Path(snapshots_dir) if snapshots_dir is not None else DEFAULT_SNAPSHOTS_DIR
    resolved_dir.mkdir(parents=True, exist_ok=True)

    json_path = resolved_dir / f"{prefix}.json"
    md_path = resolved_dir / f"{prefix}.md"

    payload = {"metrics": card["metrics"], "baseline": card["baseline"]}
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(card["markdown"], encoding="utf-8")

    return json_path, md_path
