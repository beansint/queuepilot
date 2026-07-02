"""learn/12_eval_datasets.py — D12: building an eval dataset.

Companion to docs/learn/12-eval-datasets.md. Run:

    uv run python learn/12_eval_datasets.py

Fully offline / synthetic (no CSV, no network) reproduction of the shape of
eval/dataset.py::build_eval_dataset — but in miniature and self-contained, so the
mechanics (indexed/held-out split, stratified sampling, edge-case injection, and
the leakage assertion) can be read and proven in one file.
"""

from __future__ import annotations

import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.fixtures import EDGE_CASES  # noqa: E402

SEED = 13
#: Mirrors app.config.Settings.corpus_cap: everything at index >= CAP was never
#: embedded/indexed, mirroring the real CORPUS_CAP split in eval/dataset.py.
CAP = 30


@dataclass(frozen=True)
class SyntheticRecord:
    """A tiny stand-in for data.normalize.TicketRecord."""

    id: str
    queue: str
    priority: str


def build_synthetic_records(n: int = 50) -> list[SyntheticRecord]:
    """Build n deterministic synthetic records spread across a few (queue, priority) strata."""
    queues = ["Billing", "Account", "Technical Support"]
    priorities = ["low", "high"]
    records: list[SyntheticRecord] = []
    for i in range(n):
        queue = queues[i % len(queues)]
        priority = priorities[(i // len(queues)) % len(priorities)]
        records.append(SyntheticRecord(id=f"rec-{i:03d}", queue=queue, priority=priority))
    return records


def stratified_sample(
    pool: list[SyntheticRecord], *, sample_size: int, seed: int
) -> list[SyntheticRecord]:
    """Sample ~sample_size records stratified by (queue, priority), seeded for reproducibility.

    Miniature version of eval.dataset._stratified_sample: group by stratum, allocate
    proportionally, shuffle deterministically with a seeded RNG.
    """
    groups: dict[tuple[str, str], list[SyntheticRecord]] = defaultdict(list)
    for r in pool:
        groups[(r.queue, r.priority)].append(r)

    rng = random.Random(seed)
    group_keys = sorted(groups.keys())
    total = len(pool)
    target = min(sample_size, total)

    sampled: list[SyntheticRecord] = []
    for key in group_keys:
        group = list(groups[key])
        rng.shuffle(group)
        share = round(len(group) * target / total)
        sampled.extend(group[:share])

    rng.shuffle(sampled)
    return sampled[:target]


def main() -> None:
    print("== D12: Building an eval dataset ==\n")

    # ------------------------------------------------------------------
    # 1. Synthetic corpus + the indexed/held-out split (mirrors [:CAP] / [CAP:]).
    # ------------------------------------------------------------------
    all_records = build_synthetic_records(n=50)
    indexed = all_records[:CAP]
    held_out = all_records[CAP:]

    print(f"-- Split --\n  total records   = {len(all_records)}")
    print(f"  indexed [:{CAP}]  = {len(indexed)}  (these were 'embedded' — provably in the index)")
    print(f"  held-out [{CAP}:] = {len(held_out)}  (never embedded — safe to sample from)\n")

    # ------------------------------------------------------------------
    # 2. Stratified sample from the held-out pool + edge-case injection.
    # ------------------------------------------------------------------
    sample_size = 8
    sampled = stratified_sample(held_out, sample_size=sample_size, seed=SEED)

    print(f"-- Stratified sample (n={len(sampled)}, seed={SEED}) --")
    by_stratum: dict[tuple[str, str], int] = defaultdict(int)
    for r in sampled:
        by_stratum[(r.queue, r.priority)] += 1
        print(f"  {r.id}  queue={r.queue:<18} priority={r.priority}")
    print("  per-stratum counts:", dict(sorted(by_stratum.items())))

    injected_edge_ids = [ex.id for ex in EDGE_CASES[:2]]
    print(
        f"\n-- Edge-case injection --\n  injecting {len(injected_edge_ids)} hand-authored edge "
        f"cases from eval/fixtures.py: {injected_edge_ids}"
    )
    print(
        "  (edge cases carry outputs={} — no reference labels, so exact-match evaluators "
        "skip them)"
    )

    eval_set_ids = {r.id for r in sampled} | set(injected_edge_ids)

    # ------------------------------------------------------------------
    # 3. THE LEAKAGE CHECK — the money shot.
    # ------------------------------------------------------------------
    indexed_ids = {r.id for r in indexed}
    leaked = sorted(eval_set_ids & indexed_ids)

    print("\n-- Leakage check --")
    print(f"  indexed id count = {len(indexed_ids)}, eval set id count = {len(eval_set_ids)}")
    assert not leaked, f"Leakage detected: {leaked}"
    print(
        f"  assert not leaked  ->  PASSED (0 of {len(eval_set_ids)} eval ids found "
        "in indexed set)"
    )
    print(
        "  This mirrors the real assertion in eval/dataset.py::build_eval_dataset — sampling\n"
        "  exclusively from records[CORPUS_CAP:] makes retrieval leakage structurally impossible,\n"
        "  not just a matter of not-getting-unlucky."
    )

    # Demonstrate what a LEAK would look like, without actually leaking anything above.
    poisoned_eval_ids = set(list(eval_set_ids)[:1]) | {indexed[0].id}
    would_leak = sorted(poisoned_eval_ids & indexed_ids)
    print(
        f"\n  (For contrast: if the eval set had accidentally included {indexed[0].id!r} "
        "from the\n"
        f"  indexed pool, the same check would find leaked={would_leak} and the "
        "assertion would fail\n"
        "  loudly — exactly the behavior we want if CORPUS_CAP or CSV ordering ever changes.)"
    )

    print(
        "\nTakeaway: sampling eval examples exclusively from rows beyond the indexed cap, "
        "stratifying by label, injecting edge cases, and asserting zero id overlap with the "
        "indexed set turns 'no leakage' from a hopeful convention into a provable, "
        "CI-checkable guarantee."
    )


if __name__ == "__main__":
    main()
