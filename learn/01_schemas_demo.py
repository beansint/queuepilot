"""learn/01_schemas_demo.py — A2: contract-first Pydantic models + validation.

Companion to docs/learn/01-api-contract-and-validation.md. Run:

    uv run python learn/01_schemas_demo.py

Proves: request validation (trim + reject over-limit) and a forward-compatible response envelope.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from app.schemas import AnalyzeRequest, AnalyzeResponse, SimilarTicket  # noqa: E402


def main() -> None:
    print("== A2: contract-first schemas ==\n")

    print("1) Valid request (text is trimmed):")
    req = AnalyzeRequest(text="  vpn keeps disconnecting  ", metadata={"channel": "email"})
    print(f"   text={req.text!r}  metadata={req.metadata}")

    print("\n2) Over-limit request raises ValidationError (FastAPI would return 422):")
    try:
        AnalyzeRequest(text="x" * 9000)
    except ValidationError as exc:
        print(f"   rejected -> {exc.errors()[0]['msg']}")

    print("\n3) Forward-compatible response — reserved fields default to None:")
    neighbor = SimilarTicket(score=0.91, queue="IT Support", snippet="vpn won't connect")
    resp = AnalyzeResponse(
        category="Technical",
        queue="IT Support",
        priority="High",
        confidence=0.72,
        similar_tickets=[neighbor],
    )
    reserved = ["sentiment", "sla_risk", "escalate", "clarification", "suggested_reply", "trace"]
    shown = ", ".join(f"{f}={getattr(resp, f)}" for f in reserved)
    print(f"   slice-A: category={resp.category!r} confidence={resp.confidence}")
    print(f"   reserved (None until later slices): {{{shown}}}")


if __name__ == "__main__":
    main()
