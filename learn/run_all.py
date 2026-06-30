"""Run every QueuePilot learning demo in order, with a pass/fail summary.

    uv run python learn/run_all.py

Runs each numbered concept script (``learn/NN_*.py``) in build order. Read the matching
``docs/learn/NN-*.md`` (and attempt its self-quiz) alongside each demo — see
``docs/final-build-plan/LEARNING-LOG.md`` for the full map.

Note: ``02_embeddings.py`` makes a live Voyage API call (needs ``VOYAGE_API_KEY`` in ``.env``);
the rest run fully offline.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_LEARN_DIR = Path(__file__).resolve().parent


def main() -> None:
    scripts = sorted(p for p in _LEARN_DIR.glob("[0-9]*.py"))
    if not scripts:
        print("No learning scripts found.")
        return

    results: list[tuple[str, bool]] = []
    for script in scripts:
        print(f"\n{'=' * 72}\n=== {script.name}\n{'=' * 72}")
        completed = subprocess.run([sys.executable, str(script)], check=False)  # noqa: S603
        results.append((script.name, completed.returncode == 0))

    print(f"\n{'=' * 72}\nSummary")
    for name, ok in results:
        print(f"  {'✓' if ok else '✗'} {name}")

    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"\n{len(failed)} demo(s) failed: {', '.join(failed)}")
        print("Hint: learn/02_embeddings.py needs VOYAGE_API_KEY in .env (live API call).")
        sys.exit(1)
    print("\nAll learning demos ran cleanly.")


if __name__ == "__main__":
    main()
