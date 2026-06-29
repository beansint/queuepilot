# NN — <Concept title>

> **Learning artifact** — every task that introduces a concept ships one of these.
> Pattern: `docs/learn/_TEMPLATE.md` · Log it in `docs/final-build-plan/LEARNING-LOG.md`
> Task: `<A?>` · Runnable companion: `uv run python learn/NN_<slug>.py`

Keep it short and concrete. Six fixed sections, always in this order.

## 1. Concept
Plain-language explanation of the idea, as if to a smart peer who hasn't seen it. No jargon without
a one-line definition.

## 2. In QueuePilot
Exactly where and how we use it, with file links (e.g. `app/retrieval/hybrid.py`). Tie the abstract
concept to the real code.

## 3. Why this way
The design rationale and the alternatives we rejected. Link the decision if one exists
(`docs/final-build-plan/05-DECISIONS-LOCKED.md` → `Dn`).

## 4. Verify it yourself
The runnable companion script + what to look for. The reader should be able to *prove* the concept,
not just read about it.

```bash
uv run python learn/NN_<slug>.py
```

**Expected:** <what they should see, and what it demonstrates>.

## 5. Self-quiz
2–3 questions that check real understanding (not recall). Hide answers so you actually attempt them.

1. <question?>
2. <question?>

<details><summary>Answers</summary>

1. …
2. …

</details>

## 6. Takeaway
One interview-ready sentence — the thing you'd say out loud to show you *get* it.
