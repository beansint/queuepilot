"""Eval snapshot API (Slice D follow-up) — surface ``eval/snapshots/*.json`` in-app.

Additive-only ``APIRouter`` mounted onto the main app (see ``app/main.py``). Reads the
real committed snapshot cards written by ``eval/card.py`` — never mocked, never invented
fields. Gated by the same ``require_auth`` dependency as ``POST /analyze`` so unlisted
eval data isn't exposed to unauthenticated visitors on deployments where the invite code
is configured (a no-op when auth is unconfigured, matching REST/GraphQL behavior).

See docs/final-build-plan/11-SLICE-D-DESIGN.md (D8, "console rendering... a natural
later addition") for the origin of this gap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.ratelimit import rate_limit

#: Directory containing committed snapshot cards (``<prefix>.json`` / ``<prefix>.md``
#: pairs written by ``eval.card.write_card``). Overridable in tests via monkeypatching
#: ``SNAPSHOTS_DIR`` at module scope.
SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "eval" / "snapshots"


class ReliabilityBucket(BaseModel):
    """One calibration bucket row (see ``eval/card.py`` reliability table)."""

    lo: float
    hi: float
    n: int
    claimed: float | None = None
    accuracy: float | None = None


class SnapshotMetrics(BaseModel):
    """Aggregate metrics for one eval run — mirrors the ``metrics`` dict built by
    ``eval/card.py::build_card`` (all fields optional; a partial run renders as
    ``None`` rather than being rounded up to a full score)."""

    n: int | None = None
    config: dict[str, Any] | None = None
    queue_match: float | None = None
    priority_match: float | None = None
    type_match: float | None = None
    label_recall_at_k: float | None = None
    reply_quality: float | None = None
    ece: float | None = None
    reliability: list[ReliabilityBucket] = []
    skipped_evaluators: list[str] = []


class SnapshotCard(BaseModel):
    """The full card payload for one snapshot, as committed to ``eval/snapshots/<name>.json``."""

    metrics: SnapshotMetrics
    baseline: SnapshotMetrics | None = None


class SnapshotSummary(BaseModel):
    """One row in the ``GET /eval/snapshots`` listing."""

    name: str
    n: int | None = None
    config: dict[str, Any] | None = None
    queue_match: float | None = None
    priority_match: float | None = None
    type_match: float | None = None
    label_recall_at_k: float | None = None
    reply_quality: float | None = None
    ece: float | None = None


class SnapshotListResponse(BaseModel):
    """``GET /eval/snapshots`` response envelope."""

    snapshots: list[SnapshotSummary]


router = APIRouter(
    prefix="/eval",
    tags=["eval"],
    dependencies=[Depends(require_auth), Depends(rate_limit)],
)


def _load_snapshot_json(name: str) -> dict[str, Any]:
    """Read and parse ``<SNAPSHOTS_DIR>/<name>.json``, raising a clean 404 if absent/invalid.

    ``name`` is used as a bare filename stem — no path traversal (``Path.name`` strips
    any directory components before the file is looked up).
    """
    safe_name = Path(name).name
    path = SNAPSHOTS_DIR / f"{safe_name}.json"
    try:
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"no snapshot named '{name}'")
        parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return parsed
    except (OSError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError (a subclass) and embedded-null-byte
        # names, whose filesystem probe raises ValueError — return a clean 404, not a 500.
        raise HTTPException(status_code=404, detail=f"snapshot '{name}' is unreadable") from exc


def _list_snapshot_names() -> list[str]:
    """Sorted list of snapshot name stems present in ``SNAPSHOTS_DIR`` (empty if the
    directory itself is missing — e.g. a fresh checkout before any eval run)."""
    if not SNAPSHOTS_DIR.is_dir():
        return []
    return sorted(p.stem for p in SNAPSHOTS_DIR.glob("*.json"))


@router.get("/snapshots", response_model=SnapshotListResponse)
def list_snapshots() -> SnapshotListResponse:
    """List available eval snapshots with headline summary stats for each."""
    summaries: list[SnapshotSummary] = []
    for name in _list_snapshot_names():
        try:
            payload = _load_snapshot_json(name)
        except HTTPException:
            # One unreadable/half-written card must not take down the whole listing —
            # skip it so the good snapshots still render.
            continue
        metrics = payload.get("metrics") or {}
        summaries.append(
            SnapshotSummary(
                name=name,
                n=metrics.get("n"),
                config=metrics.get("config"),
                queue_match=metrics.get("queue_match"),
                priority_match=metrics.get("priority_match"),
                type_match=metrics.get("type_match"),
                label_recall_at_k=metrics.get("label_recall_at_k"),
                reply_quality=metrics.get("reply_quality"),
                ece=metrics.get("ece"),
            )
        )
    return SnapshotListResponse(snapshots=summaries)


@router.get("/snapshots/{name}", response_model=SnapshotCard)
def get_snapshot(name: str) -> SnapshotCard:
    """Return the full card (metrics + optional baseline diff) for one snapshot."""
    payload = _load_snapshot_json(name)
    return SnapshotCard.model_validate(payload)
