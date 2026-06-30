# 05 — Blended Confidence v0 (Retrieval-Only)

> **Learning artifact** — every task that introduces a concept ships one of these.
> Pattern: `docs/learn/_TEMPLATE.md` · Log it in `docs/final-build-plan/LEARNING-LOG.md`
> Task: `A8` · Runnable companion: `uv run python learn/05_confidence_v0.py`

Keep it short and concrete. Six fixed sections, always in this order.

## 1. Concept

Confidence is a number in **[0, 1]** that tells the caller "how sure is the system about its
recommendation?"  The naive answer is to ask an LLM: "On a scale of 0–10, how confident are you?"
That is a bad idea.  LLMs are poorly calibrated — they can hallucinate certainty just as easily as
they hallucinate facts.

A better answer is to derive confidence from observable, measurable signals:

- **Label agreement**: if the top-5 retrieved historical tickets all route to "Billing", that's a
  strong signal.  If they split 2 Billing / 1 IT / 1 Security / 1 Identity, the system is
  genuinely uncertain.
- **Retrieval score**: the raw hybrid-retrieval score tells you how semantically + lexically close
  the query is to the top neighbor.  A very close match (score near or above 1 for dotproduct)
  suggests the query is well-represented in the corpus.

Blending these two signals gives a **numeric, explainable confidence** that can be shown on a
dashboard, tuned by adjusting weights, and interrogated in a debugger — unlike raw LLM output.

The formula used in v0:

```
confidence = clamp([0,1],  0.6 * agreement  +  0.4 * sigmoid(top_score))
```

Where:
- `agreement` = fraction of neighbors whose queue equals the winning queue.
- `sigmoid(top_score)` = 1 / (1 + exp(-score)), which maps any score to (0, 1).
- The clamp ensures the output is always a valid probability-like number.

## 2. In QueuePilot

The blended confidence lives in `app/analyze/baseline.py`:

- `majority_vote(neighbors)` → computes the winning queue, priority, category and the agreement
  fraction.  Pure function; no I/O.
- `confidence_v0(top_score, agreement)` → blends agreement and sigmoid-scaled score.  Pure function.
- `Analyzer.analyze(text)` → calls both after retrieval and puts the result in
  `AnalyzeResponse.confidence`.

Module constants `_W_AGREEMENT = 0.6` and `_W_SCORE = 0.4` are at the top of the file — easy to
spot and adjust.

Later slices will replace `confidence_v0` with a richer blended score that incorporates LangGraph
node outputs (classification certainty, missing-info penalties, escalation risk flags) — but the
*shape* of the output (a single `float` in `[0, 1]`) is fixed by the API contract
(`03-API-CONTRACT.md`).

## 3. Why this way

**Rejected: raw LLM self-confidence.**
LLMs produce overconfident outputs.  Their uncertainty estimates are not calibrated to actual
accuracy.  Including them directly in a production metric would mislead dashboard users and be
very hard to debug.

**Rejected: no confidence at all.**
The API contract (`03-API-CONTRACT.md`) specifies `confidence: float` in Slice A.  Skipping it
would break the contract and leave the dashboard with no signal for when to escalate.

**Chosen: blended retrieval signal.**
- Explainable: each component (agreement, score) can be displayed individually.
- Tunable: `_W_AGREEMENT` and `_W_SCORE` can be adjusted as the system is evaluated on real data.
- Offline-verifiable: no LLM call needed; tests run without network access.
- Forward-compatible: later slices add more components without changing the output shape.

Decision reference: `05-DECISIONS-LOCKED.md` D7 (no LLM in Slice A).

## 4. Verify it yourself

```bash
uv run python learn/05_confidence_v0.py
```

**Expected:**  Two scenarios printed side-by-side:

1. **High confidence** — neighbors all agree on "IT Support" + strong top-score (0.9):
   agreement = 1.0, sigmoid(0.9) ≈ 0.71, blended ≈ 0.88.
2. **Low confidence** — neighbors split across four queues + weak top-score (0.1):
   agreement = 0.25, sigmoid(0.1) ≈ 0.52, blended ≈ 0.36.

The script also verifies the clamp: agreement=1.0 + score=100 still yields confidence ≤ 1.0.

## 5. Self-quiz

1. Why does `confidence_v0` pass `top_score` through `sigmoid` before blending, rather than using
   the raw score directly?
2. If you tuned `_W_AGREEMENT` to 0.9 and `_W_SCORE` to 0.1, what would the system trust more
   when the neighbors are unanimous but the top retrieval score is weak?  Is that a good trade-off?
3. The `majority_vote` function ignores neighbor *scores* when picking the winning queue — it's a
   simple plurality vote.  When would a *weighted* vote (weight = retrieval score) give a better
   answer?  What would it cost in complexity?

<details><summary>Answers</summary>

1. Dotproduct scores from Pinecone are unbounded — a single well-matched document can return a
   score of 2.0 or higher.  Using the raw score in a linear blend would push the output outside
   [0, 1] even before the clamp.  `sigmoid` squashes any real-valued score to (0, 1) so the blend
   is well-behaved regardless of corpus or query scale.

2. With `_W_AGREEMENT = 0.9`, the system would trust the unanimous labels even though the retrieved
   evidence is weak.  This could be appropriate for narrow domains (few queues, very consistent
   routing) but risky for diverse corpora where unanimous labels on low-score neighbors might
   reflect a lack of in-distribution data rather than a clear-cut answer.

3. Weighted voting would help when, say, one very close match (score 0.95) disagrees with four
   distant matches (score 0.2 each).  A plain vote would rule in favour of the four; a weighted
   vote would favour the one.  The cost is a slightly more complex formula and the risk that a
   single high-score outlier (possibly a noisy record) dominates everything.

</details>

## 6. Takeaway

Blended numeric confidence — built from retrieval agreement and bounded score — is explainable and
tunable in a way that raw LLM self-confidence is not: every component can be logged, graphed, and
adjusted by changing a single module constant.
