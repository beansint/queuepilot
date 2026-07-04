# 11 — Slice D Design: Evaluation

Approved design pass for Milestone **M-D**. Build order maps to the D1–D14 outline on epic
`BEA-140` / GitHub #13. Decisions confirmed 2026-07-02 (see `05-DECISIONS-LOCKED.md → D15`).

## Purpose
Give the guarded copilot a **scoreboard**. Slices A–C built the workflow, the confidence blend, and
the flight recorder (LangSmith tracing + `--explain`); Slice D proves it *works* and lets us improve
it on evidence:

- **Offline eval** — a curated, held-out dataset + a suite of evaluators run via `langsmith.evaluate()`.
- **Online eval** — evaluators run against real production traces, plus a **human-feedback** path
  (thumbs + corrections) that feeds a dataset flywheel.
- **Experiments** — compare configs (alpha / prompt / chat model) side by side.
- **Calibration** — a reliability/ECE evaluator that *validates the Slice A/B confidence work*: does
  "70% confident" really mean "right ~70% of the time"? (See `docs/learn/10-rag-to-guarded-copilot.md`.)
- **Snapshot cards** — a compact per-experiment summary (JSON + Markdown) surfaced in the console.

Closes the job gap: **"LangSmith eval / experiments."**

## Decisions (confirmed — see D15)
| Topic | Choice | Rationale |
|---|---|---|
| **Judge model** | **Gemini** (different-model judge), via the existing chat registry | Groq `llama-3.3-70b` generates the suggested replies; letting it grade itself is self-preference bias. Gemini key is already configured; still free. |
| **Eval dataset** | **Post-cap held-out split** | `data/ingest.py` indexes `all_records[:CORPUS_CAP]` (first 3000 English rows). ~13k English rows sit **beyond** the cap and are provably **not** in Pinecone → zero retrieval leakage, no re-index. Sample ~150–200 stratified by queue/priority + hand-authored edge cases. |
| **Feedback path** | **`POST /feedback` API + console `FeedbackWidget`** | Endpoint starts the online-eval flywheel; the widget lives in the already-built `frontend/` console next to `SuggestedReply`. |
| **CI** | **Local runner now, CI seam later** | CI needs a LangSmith **Service** key — an ops decision that belongs with Slice E/deploy. Design the seam; don't wire it. |

## Architecture — new `eval/` package
Eval lives **out of the request path**, mirroring `learn/` and `data/`. Only the feedback path
touches `app/` (it is a runtime surface).

```
eval/
  __init__.py
  settings.py        # EvalSettings: judge model/provider, dataset name+version, sample N, recall k
  client.py          # LangSmith Client factory (reuses app.config LangSmith env wiring)
  dataset.py         # post-cap held-out sampler + edge-case fixtures + leakage assertion → JSONL
  fixtures.py        # hand-authored edge cases (empty / ambiguous / multi-issue / very-long)
  upload.py          # idempotent create_dataset + create_examples from the JSONL
  evaluators.py      # exact-match, label-recall@k, calibration, LLM-as-judge (Gemini)
  target.py          # wraps GraphAnalyzer.analyze(text) as an evaluate() target function
  run_experiment.py  # offline: evaluate() over the dataset with config knobs
  run_online.py      # online: pull recent traces (list_runs) + run evaluators + aggregate
  card.py            # experiment result → snapshot card (JSON + Markdown)
  snapshots/         # committed snapshot cards (JSON + .md), gitkept
app/
  feedback.py        # POST /feedback handler → LangSmith create_feedback + correction flywheel
frontend/src/components/console/
  FeedbackWidget.tsx # thumbs up/down + correction form, posts to /feedback
```

## Eval dataset (D2–D3)
**Source & hold-out.** Re-run `data/normalize.py` over the raw CSV to get all English `TicketRecord`s,
take the slice **at indices `CORPUS_CAP..` (i.e. `[3000:]`)** — these rows were never embedded/indexed,
so retrieval cannot have memorized them. Sample ~150–200 **stratified by `queue` × `priority`** with a
fixed seed for reproducibility. Each example:

```jsonc
{
  "inputs":  { "text": "<subject + body>", "metadata": {"source": "kaggle-heldout"} },
  "outputs": { "queue": "Technical Support", "priority": "high", "type": "Incident" }  // reference labels
}
```

**Edge cases (hand-authored, `fixtures.py`).** Injected alongside the sampled rows, tagged
`metadata.source="edge"`:
- **empty / whitespace-only** — expect graceful low-confidence + clarify/escalate, not a crash.
- **ambiguous** — vague one-liner; expect low confidence.
- **multi-issue** — two unrelated problems in one ticket; expect a sensible primary label.
- **very-long** — near `MAX_INPUT_CHARS`; expect no truncation error.

**Leakage assertion (D2).** The builder asserts none of the sampled eval ids appears in the indexed
set (the first `CORPUS_CAP` normalized ids). Fails loudly if the cap or ordering ever changes — this
is the guarantee the whole offline eval rests on.

**Versioning.** Dataset name `queuepilot-eval` with a `version` tag in `EvalSettings`; `upload.py` is
idempotent (create-if-absent, then add only missing examples keyed by input hash).

## Evaluators (D4–D6)
Modern LangSmith signature `(inputs, outputs, reference_outputs) -> dict | bool`. Deterministic ones
are pure and unit-testable offline; the judge degrades to a no-op (returns `None`, skipped) when no
Gemini key is present.

- **Exact-match (D4)** — three evaluators: `queue_match`, `priority_match`, `type_match` compare the
  `AnalyzeResponse` field to the reference label (case-insensitive). Returns `{key, score: 0/1}`.
- **Label-recall@k (D4)** — did the top-`k` retrieved neighbors include a ticket whose `queue` equals
  the reference queue? Documented **proxy** for retrieval recall (we have no gold "relevant doc ids",
  so label-recall is the honest, reproducible stand-in). Reads `similar_tickets` from the output.
- **Calibration (D5)** — *not* per-example; an **aggregate/summary evaluator** over the whole run.
  Buckets predictions by `confidence`, computes per-bucket accuracy (correct = `queue_match`) and the
  **Expected Calibration Error (ECE)** + reliability rows. Reuses the exact bucketing/ECE logic from
  `learn/10_calibration_demo.py` so the demo and the real evaluator share one implementation. This is
  the evaluator that **validates the A/B confidence blend on real outputs**.
- **LLM-as-judge (D6, Gemini)** — scores `suggested_reply` on **groundedness** (supported by the
  retrieved neighbors) and **helpfulness** (addresses the ticket) with a rubric, returning a 1–5 score
  normalized to `[0,1]`. Uses the chat registry with the judge model pinned to Gemini; wrapped
  `@traceable` so judge calls show up in the trace. No-op when Gemini is unconfigured.

## Experiment runner (D7)
`run_experiment.py` calls `client.evaluate(target, data="queuepilot-eval", evaluators=[...],
experiment_prefix=..., metadata={...}, max_concurrency=...)`.

- **Target** — `eval/target.py` wraps `GraphAnalyzer.analyze(inputs["text"])` and returns a dict of
  the fields evaluators read (`queue/priority/type/confidence/similar_tickets/suggested_reply`).
- **Config knobs** — CLI args set `alpha`, prompt variant, and `CHAT_PROVIDER`/model for the run; each
  becomes part of `experiment_prefix` + `metadata` so runs are comparable in the LangSmith UI and in
  local snapshot cards. Example: `--alpha 0.3 --chat groq` vs `--alpha 0.7 --chat groq`.
- **Output** — LangSmith experiment + a local snapshot card (D8).

## Online eval + feedback flywheel (D9–D10)
**`POST /feedback` (D9, runtime — `app/feedback.py`).** New endpoint (contract change D15):

```python
class FeedbackRequest(BaseModel):
    run_id: str                          # LangSmith run id from a prior /analyze trace.run_id
    score: int                           # thumbs: 1 (up) or 0 (down)
    correction: dict | None = None       # optional {queue?, priority?, type?} human fix
    comment: str | None = None
# → 200 {"ok": true}; 422 on bad body; graceful 200 no-op if LangSmith unconfigured (logged)
```

Handler calls `client.create_feedback(run_id, key="user_thumbs", score=score, comment=comment,
trace_id=run_id)` (non-blocking). When `correction` is present it *also* appends a corrected example
to a `queuepilot-feedback` dataset — the **flywheel**: real corrections become future eval data.

**Online eval runner (D10).** `run_online.py` uses `client.list_runs(project_name, filter=...)` to
pull recent `/analyze` root runs, runs the deterministic evaluators (+ calibration) against their
logged inputs/outputs, and prints an aggregate card. This is the "eval on real traffic" half; it needs
no dataset (it grades production runs in place).

**FeedbackWidget (D13, console).** A thumbs-up/down control + expandable correction form under the
suggested reply, posting to `/feedback` with the `trace.run_id` from the current `/analyze` response.
Disabled with a tooltip when `trace.enabled === false` (no run id to attach to). Vitest coverage.

## Snapshot cards (D8)
`card.py` turns an experiment's aggregate results into:
- **JSON** (`eval/snapshots/<prefix>.json`) — machine-readable metrics.
- **Markdown** (`eval/snapshots/<prefix>.md`) — a human "card": exact-match % per field, label-recall@k,
  judge mean, **ECE + reliability table**, config metadata, and a side-by-side diff vs a baseline card.

Console rendering of cards is a natural later addition; the committed Markdown is the v1 surface.

**Done (PR #56):** the Insights dashboard (`#/insights`, gated `GET /eval/snapshots(/{name})`,
`InsightsPage.tsx`) now renders these cards in-app, reading one pinned showcase snapshot
(`eval/snapshots/a0.5-groq.json`) committed to git so prod has real data to show.

## Learning artifacts (D11–D12) 📚
Slots already reserved in `LEARNING-LOG.md → Slice D`:
- **`11-eval` — offline vs online eval.** Doc + `learn/11_eval.py`: run a tiny **offline** eval over a
  few in-file fixtures with the deterministic evaluators (mocked target, no network) and print scores;
  then simulate **online** feedback aggregation. Proves the two modes and when each applies.
- **`12-eval-datasets` — building an eval dataset.** Doc + `learn/12_eval_datasets.py`: build a mini
  dataset from fixtures, show **stratification** + **edge-case injection** + the **leakage check**
  (assert no eval id is in the indexed set). Proves *why* held-out + no-leakage matters.

Both follow the repeatable pattern (`_TEMPLATE.md` / `_template.py`, 6 sections, self-quiz, runs via
`uv run python learn/NN_*.py` and `learn/run_all.py`).

## Envelope / contract mapping
- **No change** to `AnalyzeResponse` — eval reads existing fields.
- **New endpoint** `POST /feedback` (D15) — additive; does not touch `/analyze`. `trace.run_id`
  (Slice C) is the join key between an analysis and its feedback.

## Build order
| ID | Task | 📚 | Deps |
|---|---|---|---|
| **D1** | `eval/` scaffold + `EvalSettings` (judge=Gemini, dataset name/ver, sample N, k) + LangSmith `Client` factory | | — |
| **D2** | Dataset builder: post-cap stratified sampler + edge-case fixtures + **leakage assertion** → versioned JSONL | | D1 |
| **D3** | LangSmith dataset upload (idempotent `create_dataset` + `create_examples`) | | D2 |
| **D4** | Deterministic evaluators: exact-match (queue/priority/type) + label-recall@k | | D1 |
| **D5** | Calibration evaluator: ECE / reliability over blended confidence (validates A/B) | | D4 |
| **D6** | LLM-as-judge (Gemini) for `suggested_reply`; graceful no-op without key | | D1 |
| **D7** | Experiment runner: `evaluate()` over dataset + config knobs (alpha/prompt/model) | | D3–D6 |
| **D8** | Eval snapshot cards → JSON + Markdown + side-by-side diff | | D7 |
| **D9** | `POST /feedback` → LangSmith `create_feedback` + correction flywheel dataset **(D15)** | | D1 |
| **D10** | Online eval runner: `list_runs` recent traces + evaluators + aggregate | | D4,D5 |
| **D11** | 📚 `11-eval` (offline vs online) — doc + `learn/11_eval.py` + quiz + log row | 📚 | D7,D10 |
| **D12** | 📚 `12-eval-datasets` — doc + `learn/12_eval_datasets.py` + quiz + log row | 📚 | D2 |
| **D13** | Frontend `FeedbackWidget` (thumbs + correction) → `POST /feedback` + vitest | | D9 |
| **D14** | Backend tests: evaluators (+calibration math), leakage, `/feedback` mocked, judge mocked, 1 gated live eval | | all |

## Constraints
- **Eval is out of the request path.** Nothing in `eval/` is imported by `/analyze`; a broken evaluator
  can never 500 a request.
- **Offline-testable.** Deterministic evaluators and the dataset builder run with zero network; the
  judge and live `evaluate()`/`create_feedback` calls are gated behind a LangSmith/Gemini key (one
  gated live integration test, mirroring the Slice B/C pattern).
- **No leakage.** The offline dataset is drawn strictly from post-cap rows; D2's assertion enforces it.
- **Graceful degradation.** `/feedback` returns `200` and logs a no-op when LangSmith is unconfigured;
  the judge is skipped without a Gemini key.
- **Honest metrics.** Label-recall@k is documented as a proxy (no gold relevant-doc ids); snapshot
  cards state N, config, and any skipped evaluators — never round a partial run up to a full score.
- **CI deferred.** The runner is local/manual (Personal token). The CI seam (Service key, nightly
  Action) is documented for Slice E, not wired here.
