"""QueuePilot offline/online evaluation package (Slice D).

Lives out of the request path — nothing under ``app/`` imports from ``eval/``; a broken
evaluator can never affect ``/analyze``. See ``docs/final-build-plan/11-SLICE-D-DESIGN.md``.
"""

from __future__ import annotations
