"""learn/06_langgraph_state.py — B1: how state threads through a LangGraph StateGraph.

Companion to docs/learn/06-langgraph-state.md. Run:

    uv run python learn/06_langgraph_state.py

Proves: each node returns a PARTIAL state dict, which LangGraph merges into the running state.
No network — a toy 2-node graph.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import END, START, StateGraph  # noqa: E402


class ToyState(TypedDict, total=False):
    text: str
    steps: list[str]


def shout(state: ToyState) -> dict[str, object]:
    """Node A: uppercase the text and record that we ran."""
    return {"text": state["text"].upper(), "steps": [*state.get("steps", []), "shout"]}


def bang(state: ToyState) -> dict[str, object]:
    """Node B: append '!' and record that we ran."""
    return {"text": state["text"] + "!", "steps": [*state.get("steps", []), "bang"]}


def main() -> None:
    print("== B1: LangGraph state merge ==\n")

    builder = StateGraph(ToyState)
    builder.add_node("shout", shout)
    builder.add_node("bang", bang)
    builder.add_edge(START, "shout")
    builder.add_edge("shout", "bang")
    builder.add_edge("bang", END)
    graph = builder.compile()

    print("input:   {'text': 'hello'}")
    result = graph.invoke({"text": "hello"})
    print(f"output:  {result}")
    print("\nEach node returned only the keys it changed; LangGraph merged them in order:")
    print(f"  text  : 'hello' -> 'HELLO' (shout) -> 'HELLO!' (bang)  =>  {result['text']!r}")
    print(f"  steps : accumulated across nodes  =>  {result['steps']}")


if __name__ == "__main__":
    main()
