"""learn/15_graphql.py — REST vs GraphQL, proven with QueuePilot's own schema (Slice F).

Runs standalone + offline (the LangGraph analyzer is faked — no network):

    uv run python learn/15_graphql.py

What it proves:
  1. The Pydantic ``AnalyzeResponse`` envelope becomes a typed GraphQL schema (printed SDL).
  2. Field selection: two queries hit the SAME resolver / SAME server compute, but the client
     controls the response shape — one asks for 2 fields, one for the whole envelope.
  3. The server work is identical either way — GraphQL saves bytes on the wire + client code,
     NOT backend compute (the graph runs the same regardless of selected fields).

Pair: docs/learn/15-graphql.md + a row in docs/final-build-plan/LEARNING-LOG.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Standalone scripts run from learn/, so put the project root on sys.path for `import app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import AnalyzeResponse, SimilarTicket  # noqa: E402

# A canned analyzer result so the demo is offline (no Pinecone / LLM). This is exactly the
# envelope a real `/analyze` would produce; the resolver maps it to the GraphQL `Analysis` type.
_CANNED = AnalyzeResponse(
    category="Incident",
    queue="Billing and Payments",
    priority="low",
    confidence=0.841,
    similar_tickets=[
        SimilarTicket(score=0.42, queue="Billing and Payments", priority="low",
                      type="Incident", snippet="charged twice for my subscription"),
    ],
    sentiment={"frustration": 0.3, "negativity": 0.2},
    sla_risk=0.18,
    escalate=False,
    clarification=None,
    suggested_reply="Thanks for flagging the duplicate charge — I can see two charges …",
    trace={"enabled": False},
)


class _FakeAnalyzer:
    calls = 0

    def analyze(self, text: str, *, explain: bool = False) -> AnalyzeResponse:
        # Count invocations to PROVE both queries do the same server work.
        _FakeAnalyzer.calls += 1
        return _CANNED


def main() -> None:
    # Patch the resolver's analyzer BEFORE importing the schema module's dependency graph.
    import app.graphql.schema as gql

    fake = _FakeAnalyzer()
    gql.get_graph_analyzer = lambda: fake  # type: ignore[assignment]
    schema = gql.schema

    print("== 1. The Pydantic envelope, as a typed GraphQL schema (SDL) ==\n")
    print(schema.as_str())

    print("\n== 2. Field selection — the CLIENT picks the shape ==\n")

    slim = "{ analyze(text: \"charged twice\") { queue confidence } }"
    slim_result = schema.execute_sync(slim)
    print("Query A (triage widget) asks for 2 fields:")
    print("  ", slim)
    print("  →", slim_result.data)

    full = (
        "{ analyze(text: \"charged twice\") { category queue priority confidence "
        "similarTickets { score snippet } sentiment { frustration negativity } "
        "slaRisk escalate suggestedReply trace } }"
    )
    full_result = schema.execute_sync(full)
    print("\nQuery B (full console) asks for the whole envelope:")
    print("  →", full_result.data)

    print("\n== 3. Same server compute, different wire shape ==\n")
    print(f"Resolver ran {_FakeAnalyzer.calls} times — once per query.")
    print("Query A shipped", len(str(slim_result.data)), "chars;",
          "Query B shipped", len(str(full_result.data)), "chars.")
    print("→ The graph did the SAME work both times. GraphQL saved bytes + client code on A,")
    print("  NOT backend compute. That's the honest scope of what field-selection buys you.")


if __name__ == "__main__":
    main()
