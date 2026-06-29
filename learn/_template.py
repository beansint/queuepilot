"""learn/_template.py — copy this for every runnable concept script.

The script must:
  * run standalone:  uv run python learn/NN_<slug>.py
  * isolate ONE concept (no full-app dependencies beyond what the concept needs)
  * print observable output that PROVES the concept (numbers, shapes, before/after)
  * be safe to run repeatedly and offline where possible

Pair it with docs/learn/NN-<slug>.md and a row in docs/final-build-plan/LEARNING-LOG.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Standalone scripts run from learn/, so put the project root on sys.path for `import app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    print("== <concept> ==")
    # 1. set up the smallest possible example
    # 2. run the thing
    # 3. print what happened and why it matters
    raise NotImplementedError("copy this template; implement the concept demo")


if __name__ == "__main__":
    main()
