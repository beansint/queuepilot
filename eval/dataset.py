"""Offline eval dataset builder (D2).

Builds a leakage-free, stratified sample of held-out (never-embedded) tickets plus
hand-authored edge cases, and serializes them to JSONL.

Leakage guarantee (best-effort, structural check only): ``data/ingest.py`` is *intended*
to index only ``records[:settings.corpus_cap]`` (the first ``CORPUS_CAP`` normalized
English rows, in CSV order), so sampling eval examples exclusively from the tail beyond
that cut is designed to avoid retrieval leakage. This ASSUMES the live Pinecone index was
actually built with the current ``settings.corpus_cap`` — the assertion below only
verifies this module's own slice arithmetic (that the sampled ids don't fall in
``records[:cap]``); it cannot see what Pinecone actually contains. If ingest was ever run
with a different ``--cap`` (e.g. a larger value than the current ``settings.corpus_cap``),
rows between the two caps were embedded into the index but this code would still treat
them as held-out — real leakage this assertion cannot detect. Keep ingest's cap and
``settings.corpus_cap`` in sync, or re-run ingest, whenever this guarantee matters.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from data.normalize import TicketRecord, load_rows, normalize_rows

#: Default raw CSV path (see docs/final-build-plan/07-DATASET.md).
DEFAULT_CSV_PATH = "data/raw/aa_dataset-tickets-multi-lang-5-2-50-version.csv"

#: Default output path for the built dataset.
DEFAULT_JSONL_PATH = "eval/datasets/queuepilot-eval-v1.jsonl"


class EvalExample(BaseModel):
    """One eval dataset row: an input ticket plus (optional) reference labels."""

    id: str
    inputs: dict[str, Any]  # {"text": str, "metadata": dict}
    outputs: dict[str, Any]  # reference labels {"queue","priority","type"} or {} for edge cases
    source: str  # "kaggle-heldout" | "edge"


def _record_to_example(record: TicketRecord, *, source: str) -> EvalExample:
    """Map a normalized ``TicketRecord`` to an ``EvalExample`` with reference labels."""
    return EvalExample(
        id=record.id,
        inputs={"text": record.text, "metadata": {"source": source}},
        outputs={
            "queue": record.queue,
            "priority": record.priority,
            "type": record.type,
        },
        source=source,
    )


def _stratified_sample(
    records: list[TicketRecord], *, sample_size: int, seed: int
) -> list[TicketRecord]:
    """Sample ~``sample_size`` records stratified by ``(queue, priority)``.

    Only records with both ``queue`` and ``priority`` set are eligible (they are the
    ones that can serve as reference examples for the exact-match evaluators). Uses a
    seeded ``random.Random`` so sampling is fully reproducible.
    """
    eligible = [r for r in records if r.queue is not None and r.priority is not None]
    if not eligible:
        return []

    groups: dict[tuple[str, str], list[TicketRecord]] = defaultdict(list)
    for r in eligible:
        assert r.queue is not None and r.priority is not None
        groups[(r.queue, r.priority)].append(r)

    rng = random.Random(seed)
    # Deterministic group iteration order regardless of dict insertion order.
    group_keys = sorted(groups.keys())

    # Proportional allocation per stratum, rounded, then trimmed/topped-up to hit
    # sample_size exactly (bounded by len(eligible)).
    total = len(eligible)
    target = min(sample_size, total)

    allocations: dict[tuple[str, str], int] = {}
    for key in group_keys:
        group = groups[key]
        share = round(len(group) * target / total)
        allocations[key] = min(share, len(group))

    sampled: list[TicketRecord] = []
    for key in group_keys:
        group = list(groups[key])
        rng.shuffle(group)
        sampled.extend(group[: allocations[key]])

    # Top up / trim to hit `target` exactly, deterministically.
    if len(sampled) > target:
        rng.shuffle(sampled)
        sampled = sampled[:target]
    elif len(sampled) < target:
        # Track already-sampled ids in a set for O(1) membership tests instead of an
        # O(n) linear scan with full pydantic-model equality per candidate (O(n*m)
        # overall) — ids are unique per TicketRecord, so this preserves identical results.
        sampled_ids = {r.id for r in sampled}
        remaining_pool = [r for r in eligible if r.id not in sampled_ids]
        rng.shuffle(remaining_pool)
        sampled.extend(remaining_pool[: target - len(sampled)])

    rng.shuffle(sampled)
    return sampled


def build_eval_dataset(
    *,
    csv_path: str | Path | None = None,
    sample_size: int | None = None,
    seed: int | None = None,
) -> list[EvalExample]:
    """Build the full eval dataset: stratified held-out sample + hand-authored edge cases.

    Args:
        csv_path: Raw Kaggle CSV path. Defaults to ``DEFAULT_CSV_PATH``.
        sample_size: Held-out rows to sample. Defaults to ``EvalSettings.sample_size``.
        seed: RNG seed for stratified sampling. Defaults to ``EvalSettings.seed``.

    Returns:
        Combined list of held-out ``EvalExample`` rows (tagged ``"kaggle-heldout"``)
        plus the fixed ``EDGE_CASES`` (tagged ``"edge"``).

    Raises:
        AssertionError: if any sampled example id collides with an id in
            ``records[:settings.corpus_cap]`` per this module's own slice arithmetic. This
            is a best-effort structural check, not proof against Pinecone — see the module
            docstring for the assumption it rests on (ingest was run with the current
            ``settings.corpus_cap``).
    """
    from eval.fixtures import EDGE_CASES  # local import: avoids a circular import at module load
    from eval.settings import get_eval_settings

    eval_settings = get_eval_settings()
    resolved_csv_path = csv_path if csv_path is not None else DEFAULT_CSV_PATH
    resolved_sample_size = sample_size if sample_size is not None else eval_settings.sample_size
    resolved_seed = seed if seed is not None else eval_settings.seed

    rows = load_rows(resolved_csv_path)
    records, _stats = normalize_rows(rows)

    cap = get_settings().corpus_cap
    indexed_records = records[:cap]
    held_out_records = records[cap:]

    indexed_ids = {r.id for r in indexed_records}

    sampled = _stratified_sample(
        held_out_records, sample_size=resolved_sample_size, seed=resolved_seed
    )

    leaked = [r.id for r in sampled if r.id in indexed_ids]
    assert not leaked, (
        f"Leakage detected: {len(leaked)} sampled eval example id(s) are present in the "
        f"indexed set (records[:{cap}]). This must never happen — it means the held-out "
        f"cut (CORPUS_CAP) or CSV ordering changed. Leaked ids: {leaked[:5]}..."
    )

    examples = [_record_to_example(r, source="kaggle-heldout") for r in sampled]
    examples.extend(EDGE_CASES)
    return examples


def write_jsonl(examples: list[EvalExample], path: str | Path = DEFAULT_JSONL_PATH) -> None:
    """Write *examples* to *path*, one JSON object per line."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for example in examples:
            f.write(
                json.dumps(
                    {
                        "id": example.id,
                        "inputs": example.inputs,
                        "outputs": example.outputs,
                        "source": example.source,
                    }
                )
            )
            f.write("\n")


def read_jsonl(path: str | Path = DEFAULT_JSONL_PATH) -> list[EvalExample]:
    """Read eval examples previously written by ``write_jsonl``."""
    in_path = Path(path)
    examples: list[EvalExample] = []
    with in_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            examples.append(EvalExample.model_validate_json(line))
    return examples


if __name__ == "__main__":
    built = build_eval_dataset()
    write_jsonl(built)
    print(f"Wrote {len(built)} examples to {DEFAULT_JSONL_PATH}")
