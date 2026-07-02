# 11 — Offline vs online eval

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `D11` · Runnable companion: `uv run python learn/11_eval.py`

## 1. Concept

**Offline eval** runs a *fixed target* (the pipeline under test, unchanged mid-run) over a *curated
dataset* with known reference labels, scored by a suite of *evaluators*. It's reproducible — same
inputs, same target, same evaluators → the same numbers every time — which makes it the right tool
for pre-deploy questions: "did this prompt change help or hurt?", "is alpha=0.5 better than alpha=0.7
for retrieval?". Its weakness is the dataset itself: it can only ever be as representative as whatever
was curated into it, and it can't see failure modes nobody thought to write a fixture for.

**Online eval** grades *real production traces* — actual `/analyze` calls with actual user inputs —
plus *human feedback* (thumbs up/down, corrections) collected after the fact. It sees the true traffic
distribution, including inputs nobody anticipated, but it's noisier (no clean reference labels, humans
disagree or don't notice mistakes) and it's inherently post-deploy: you're grading what already
shipped, not gating what's about to ship.

Neither replaces the other. Offline eval is the pre-merge gate; online eval is the feedback loop that
tells you whether the offline dataset itself still matches reality — and, via corrections, becomes the
next offline dataset.

## 2. In QueuePilot

- **Offline** — `eval/run_experiment.py` calls `client.evaluate(target, data="queuepilot-eval",
  evaluators=[...])` against the held-out dataset built by `eval/dataset.py`
  (`docs/learn/12-eval-datasets.md`). The evaluators themselves are pure functions:
  `eval/evaluators/deterministic.py` (`queue_match`, `priority_match`, `type_match`,
  `label_recall_at_k`) and `eval/evaluators/calibration.py` (`calibration_summary` — validates the
  Slice A/B confidence blend against real predictions). `eval/target.py` wraps
  `GraphAnalyzer.analyze` so the target function under evaluation is the exact same code path
  production hits. Results land in a snapshot card (`eval/card.py` → `eval/snapshots/`).
- **Online** — `eval/run_online.py` calls `client.list_runs(project_name, filter=...)` to pull recent
  `/analyze` root runs straight out of LangSmith, then runs the same deterministic evaluators against
  each run's already-logged inputs/outputs — no dataset, no fixed target, just grading what actually
  happened in production.
- **The flywheel** — `POST /feedback` (`app/feedback.py`, `app/main.py`) is the human half of online
  eval: a caller posts `{run_id, score, correction?}`, which calls
  `client.create_feedback(run_id, key="user_thumbs", score=score)` on the matching LangSmith trace
  (joined via `trace.run_id` from Slice C, see `docs/learn/08-langsmith-tracing.md`). When a
  `correction` is supplied, the handler *also* appends a corrected example to a
  `queuepilot-feedback` LangSmith dataset — a real production mistake, now future eval data.

## 3. Why this way

- **Why not just online eval?** Without a fixed target and fixed dataset there's no controlled A/B —
  you can't tell whether a metric moved because the model changed or because this week's traffic mix
  changed. Offline eval isolates the variable you're testing.
- **Why not just offline eval?** The Kaggle-derived dataset (`docs/final-build-plan/07-DATASET.md`)
  is a snapshot; real tickets drift in phrasing, new products, new failure modes. Online eval is the
  only way to notice that drift, and `POST /feedback` corrections are the only way real users' actual
  disagreements ever reach the dataset (`docs/final-build-plan/05-DECISIONS-LOCKED.md → D15`).
- **Why is calibration only meaningful as a *summary* evaluator, not per-example?** "Is 70% confidence
  really right 70% of the time" is a statement about a *distribution* of predictions, not any single
  one — see `eval/evaluators/calibration.py::calibration_summary`, which buckets the *whole run* and
  computes Expected Calibration Error (ECE), not a per-row score.
- **Why is `/feedback` a separate endpoint instead of folded into `/analyze`?** Different verb
  (grading vs. predicting), different audience (a human reacting after the fact vs. a caller wanting a
  prediction), and different lifecycle (feedback can arrive minutes or days after the original call).
  Locked in `05-DECISIONS-LOCKED.md → D15`.

## 4. Verify it yourself

```bash
uv run python learn/11_eval.py
```

**Expected:** No network, no LLM, no LangSmith. The script imports the *real*
`queue_match`/`priority_match`/`type_match`/`label_recall_at_k` from `eval.evaluators.deterministic`
and runs them over three in-file fixtures against a canned mock target (one is an intentional miss,
so you see a 0.0 score alongside two 1.0s) — this is "offline eval" in miniature. It then aggregates a
small simulated stream of thumbs feedback into a `satisfaction_rate`, alongside a `true_accuracy`
computed from ground truth that the thumbs *don't* have access to, printing the gap between them
("thumbs-up-but-wrong") — proving why online eval alone would miss what offline eval catches, and
vice versa.

## 5. Self-quiz

1. `label_recall_at_k` and `queue_match` both compare against `reference_outputs["queue"]`. Why does
   QueuePilot need both instead of just one?
2. The online-eval simulation in `learn/11_eval.py` shows `satisfaction_rate = 0.714` but
   `true_accuracy = 0.571`. Which of the two would `eval/run_experiment.py` (offline) report, and
   which would `eval/run_online.py` + `POST /feedback` (online) report — and why can online eval's
   number diverge from ground truth in a way offline eval's can't?
3. If you deleted the held-out dataset entirely and relied only on `POST /feedback` corrections as
   your eval set, what property from `docs/learn/12-eval-datasets.md` (the leakage guarantee) would
   you lose, and why does that matter?

<details><summary>Answers</summary>

1. `queue_match` scores the *classification* label directly (did the pipeline's predicted `queue`
   equal the reference `queue`). `label_recall_at_k` scores *retrieval* — whether any of the top-k
   `similar_tickets` neighbors carried the reference queue label, a proxy for "did retrieval surface
   relevant context" since there are no gold relevant-document ids for the Kaggle corpus. A pipeline
   can classify correctly with poor retrieval (LLM parametric knowledge covered for it) or retrieve
   well but classify wrong (LLM ignored good context) — the two evaluators catch different failures.
2. Offline eval (`run_experiment.py`) would report `true_accuracy`-style numbers, because it always
   has reference labels to compare against — `queue_match` etc. only ever emit a hard 0/1 against
   ground truth. Online eval (`run_online.py` + `/feedback`) reports something closer to
   `satisfaction_rate`, because it has no reference labels for live traffic — only what a human
   *believed* was correct at the moment they clicked thumbs-up, which can diverge from truth when the
   error wasn't obvious to the user (the "thumbs-up-but-wrong" rows).
3. You'd lose the guarantee that eval examples were never seen during indexing/embedding (zero
   retrieval leakage). Feedback corrections come from real production traces, which by definition ran
   against the live index — so a correction dataset alone can't tell you "does retrieval generalize to
   unseen tickets," only "does the pipeline get *previously-seen-shaped* tickets right." You'd need
   the held-out split back to make that claim honestly.

</details>

## 6. Takeaway

"Offline eval is a reproducible, pre-deploy gate — fixed target, fixed dataset, deterministic
evaluators, same numbers every run — while online eval grades real production traffic and human
feedback post-deploy; QueuePilot runs both (`eval/run_experiment.py` + `eval/run_online.py` +
`POST /feedback`) because each sees a failure mode the other structurally cannot."
