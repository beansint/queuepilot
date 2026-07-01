# 10 — From classic RAG to a guarded agentic copilot

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: overview (Slices A–C) · Runnable companion: `uv run python learn/10_calibration_demo.py`

Written for someone who already knows **classic RAG** (embed → vector-search → stuff into a
prompt → generate) and wants to understand the pieces QueuePilot adds on top.

---

## 1. Concept

Classic RAG answers a question:

```
"Is a backward pass legal?"
     │  embed
     ▼
 ┌───────────────┐  top-k chunks   ┌────────────────────┐
 │ vector search │────────────────►│ LLM reads + writes │──► answer + citation
 └───────────────┘                 └────────────────────┘
```

QueuePilot is this exact loop with **five upgrades**. Each one is a small, nameable idea.

### Upgrade 1 — retrieve with *two* matchers (hybrid retrieval)

Embeddings match by **meaning**; they can miss **exact terms** (a law number, an error code,
a product name). So we add an old-school **keyword matcher (BM25)** and blend both:

```
              ┌─ dense (meaning) ─► "VPN won't connect" ≈ "can't reach network"
 ticket text ─┤
              └─ sparse/BM25 ─────► exact tokens: "GlobalProtect", "22H2", "Law 11"

     blend → hybrid_score_norm(alpha) → semantic recall + keyword precision
```

Gotcha: the two scores live on different scales, so you **normalize before blending** or one
drowns out the other. `alpha` is the dial (1.0 = pure meaning, 0.0 = pure keywords).

### Upgrade 2 — the LLM fills in a *form*, not a paragraph (structured output)

```
Classic RAG:   "Yes, a backward pass is legal because…"
QueuePilot :   category=Incident · queue=Technical Support · priority=High · sentiment={frustration:0.72}
```

Same retrieve-and-read, but the output is **decisions a system can act on**, not prose.

### Upgrade 3 — split the prompt into an *assembly line* (the agent / LangGraph)

```
 ticket ─► retrieve ─► classify ─► sentiment ─► assess_missing ─► score ─► decide
           (similar)   (labels)    (how upset)  (enough info?)    (trust?) (route)
```

Each box is a **node**; they share a **state** dict that accumulates results. Because the work
is broken into steps, you can *see what each step contributed* — which powers Upgrade 5.

### Upgrade 4 — a *real* trust score (calibrated confidence) ⭐ the big one

**Trap:** ask an LLM "how sure are you?" and it says "very!" almost every time, whether right
or wrong. LLMs are **overconfident / badly calibrated**, so self-reported confidence is noise.

**Fix:** never ask the model. Build trust from things you can **observe**:

```
 confidence = 0.5 × (do retrieved neighbours AGREE?)     # consensus = evidence
            + 0.3 × sigmoid(top match CLOSENESS)         # a 0.9 hit > a 0.3 hit
            + 0.2 × (LLM agrees with the majority?)       # cheap cross-check
            − 0.15 × (were details MISSING?)              # penalty
```

Referee analogy: a ref who yells "100% certain!" every call is useless. Trustworthy confidence
comes from *did other refs agree* and *was it a clear-cut view* — not from how loud the ref is.

### Upgrade 5 — know when *not* to answer + show the work (guarded routing + explainability)

With a real confidence number, the last node **routes** instead of always answering:

```
   0 ────────────────────────────────────────────── 1   confidence
   │  ESCALATE  │      CLARIFY      │      ANSWER      │
   0          0.35                0.62                 1
                ▲ you are here (0.13) → hand to a human
```

- low trust → **escalate** to a human · missing info → **ask** · high trust → **answer**
  (grounded in the retrieved tickets, so fewer hallucinations).
- **Explainability**: the `--explain` panel is literally the confidence formula itemized + the
  per-node trace. **Tracing** (LangSmith) is a flight recorder: you can't unit-test an LLM
  (same input → different output), so you record every run and evaluate in aggregate instead.

The whole picture:

```
 ticket ─► HYBRID retrieve ─► assembly-line of LLM steps ─► REAL confidence ─► ROUTE
           (meaning+words)     (classify/sentiment/…)       (measured, not      (answer/
                                                             self-reported)      clarify/
                                                                                 escalate)
                     └────────── every step traced + explainable ──────────┘
```

## 2. In QueuePilot

- Hybrid retrieval → `app/retrieval/` (`hybrid.py`, `sparse.py`, `pinecone_store.py`).
- Assembly line → `app/analyze/graph.py` (LangGraph nodes + state).
- Calibrated confidence → `app/analyze/scoring.py` (`full_confidence_breakdown`, `sla_risk_breakdown`).
- Routing → `route_decision` in `app/analyze/graph.py` (confidence-primary).
- Tracing + `--explain` → `app/analyze/trace.py`, `graph_analyzer.py`; surfaced in the console.

## 3. Why this way

- Self-confidence is uncalibrated, so we **engineer** a confidence signal from retrieval
  agreement + closeness (a tiny ensemble) — see `05-DECISIONS-LOCKED.md → D7`.
- A guarded copilot that escalates under uncertainty is more trustworthy than one that always
  answers — helping under uncertainty without over-committing (`00-MASTER-SPEC.md`).

## 4. Verify it yourself

```bash
uv run python learn/10_calibration_demo.py
```

**Expected:** a simulated LLM that *claims* ~95% confidence turns out right only ~half the time
(large "calibration error"), while the **blended** score's buckets line up with real accuracy
(small error) — i.e. "70% confident" really means "right ~70% of the time." It imports the real
`full_confidence_breakdown`, so the blended number is exactly what `/analyze?explain=true` shows.

## 5. Self-quiz

1. Why don't we use the LLM's self-reported confidence, and what do we use instead?
2. What breaks if you blend dense + sparse retrieval scores without normalizing first?
3. Why is "escalate under uncertainty" a feature, not a limitation?

<details><summary>Answers</summary>

1. LLMs are miscalibrated (systematically overconfident), so self-confidence doesn't track
   correctness. We blend observable signals — neighbour agreement, retrieval closeness,
   LLM-vs-majority consistency, minus a missing-info penalty — into a score that does.
2. The larger-magnitude score dominates, so `alpha` no longer controls the dense/sparse
   trade-off; you effectively get single-mode retrieval and lose the hybrid benefit.
3. A copilot that hands off when genuinely unsure (or when SLA risk is extreme) avoids
   confident-but-wrong actions on real operations. Trustworthy behaviour under uncertainty is
   worth more than always answering.
</details>

## 6. Takeaway

Classic RAG retrieves and generates; a **guarded agentic copilot** also decides *how much to
trust itself* (from measured signals, not the model's word) and *what to do about it* (answer,
ask, or escalate) — and can show its work. Internalising **calibration** alone puts you ahead of
most people entering AI/ML.
