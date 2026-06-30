# 07 — Guarded-copilot pattern (answer / clarify / escalate)

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `B8` · Runnable companion: `uv run python learn/07_guarded_copilot.py`

## 1. Concept

A **guarded copilot** is an AI assistant that refuses to guess when it isn't confident.
Instead of always producing an answer (and sometimes producing a wrong or hallucinated one),
it routes each ticket to one of three outcomes:

| Route | When | Action |
|---|---|---|
| **answer** | High confidence, no missing info, low SLA risk | Draft a grounded reply for the agent to send. |
| **clarify** | Enough confidence but key details are missing | Ask 1–2 targeted questions before attempting a reply. |
| **escalate** | Low confidence OR high SLA risk | Hand off to a human agent immediately. |

The key insight is that **not answering is better than answering wrongly**. A support agent
who sees an escalated ticket knows they need to investigate; an agent who sees a confident-but-
wrong suggested reply may send it without checking.

The decision is computed from two numeric scores:

- **Confidence** — blends retrieval agreement, top-neighbor similarity, LLM/majority label
  consistency, and a missing-info penalty.
- **SLA risk** — blends priority tier, customer frustration, and presence of missing info.

Both scores are deterministic (no LLM) and expressed as floats in [0, 1].
Thresholds (module constants in `app/analyze/graph.py`) turn them into a routing decision.

## 2. In QueuePilot

The pattern lives in `app/analyze/graph.py` and `app/analyze/scoring.py`:

- `app/analyze/scoring.py` — `full_confidence(...)` and `sla_risk(...)`: pure, testable functions.
- `app/analyze/graph.py` — `route_decision(confidence, sla_risk_score, missing_info) -> str`:
  pure routing helper; importable without instantiating the full graph.
- Inside `build_graph(...)`:
  - `score` node — calls `full_confidence` and `sla_risk`; no LLM.
  - `decide` node — calls `route_decision`; stores `decision` and `escalate` in state.
  - Conditional edge on `decide` → branches to `draft_reply`, `clarify`, or `END`.
  - `draft_reply` node — LLM (`chat_model.complete`) grounds reply in neighbor snippets.
  - `clarify` node — LLM (`chat_model.complete_json`) generates 1–2 targeted questions.

Graph shape:

```
START → retrieve → classify → sentiment → assess_missing → score → decide ◇
                                                                     ├ answer   → draft_reply → END
                                                                     ├ clarify  → clarify     → END
                                                                     └ escalate → END
```

Constants that control behaviour:
- `ESCALATE_CONFIDENCE_BELOW = 0.4`
- `ESCALATE_SLA_RISK_ABOVE = 0.7`

## 3. Why this way

**Why three routes instead of two?** Collapsing clarify into escalate would send more tickets to
humans needlessly. Collapsing clarify into answer would produce incomplete replies and confuse
customers. The three-way split matches real support workflow.

**Why thresholds on interpretable numbers?** Raw LLM self-confidence ("I'm 80% sure") is neither
calibrated nor auditable. Our confidence and SLA risk scores are derived from observable signals
(retrieval agreement, neighbor scores, priority labels) that a human can inspect and tune. The
thresholds become product knobs — raise `ESCALATE_CONFIDENCE_BELOW` to be more conservative,
lower it to auto-answer more aggressively.

**Why is the routing function pure?** `route_decision` takes three numbers and returns a string.
It is trivially unit-tested, trivially explained in a post-mortem ("we escalated because
confidence=0.32 < 0.4"), and importable without spinning up the graph. This is decision D5's
"explainability" principle applied to control flow.

**Why not let the LLM decide when to escalate?** LLMs are uncalibrated, non-deterministic, and
can be prompted into overconfidence. The scoring layer is the safety net that the LLM cannot
bypass.

## 4. Verify it yourself

```bash
uv run python learn/07_guarded_copilot.py
```

**Expected:** Five synthetic tickets are scored and routed. You should see at least one of each
route — ANSWER, CLARIFY, and ESCALATE — with the numeric (confidence, sla_risk) pair that drove
the decision. The script imports `route_decision` from the real app code, so it proves the logic
is exactly what runs in production.

## 5. Self-quiz

1. A ticket has `confidence=0.55` and `sla_risk=0.75`. Which route does it take, and why? Would
   adding one missing-info item change the route?
2. If the LLM classify node disagrees with the majority-vote queue, how does that affect
   confidence, and what does that mean for the routing decision?
3. Why is the `score` node placed *before* `decide` rather than computing the scores inside
   `decide` itself?

<details><summary>Answers</summary>

1. It escalates: `sla_risk=0.75 > ESCALATE_SLA_RISK_ABOVE (0.7)`. Adding a missing-info item
   would make no difference — the escalation is triggered by SLA risk, not missing info.
   (The decision check is `OR`: either condition is sufficient to escalate.)
2. A queue mismatch means `consistency=0.0` instead of `W_CONSISTENCY=0.2`, so
   `full_confidence` drops by 0.2. That makes escalation more likely by pushing confidence
   closer to or below the `ESCALATE_CONFIDENCE_BELOW=0.4` threshold.
3. Separation of concerns: `score` is a deterministic, LLM-free node that produces measurable
   floats. Keeping it separate makes it individually unit-testable and its output observable in
   LangSmith traces (Slice C). If scoring were buried inside `decide`, you would lose the
   intermediate signal.

</details>

## 6. Takeaway

"A guarded copilot escalates under uncertainty rather than guessing — the answer/clarify/escalate
decision is driven by interpretable, auditable numbers (confidence and SLA risk), not by asking
the LLM to rate its own confidence."
