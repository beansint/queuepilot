# 12 — Building an eval dataset

> **Learning artifact** — Pattern: `docs/learn/_TEMPLATE.md` · Log: `docs/final-build-plan/LEARNING-LOG.md`
> Task: `D12` · Runnable companion: `uv run python learn/12_eval_datasets.py`

## 1. Concept

An eval dataset is only trustworthy if it measures the thing you actually care about: "does this
pipeline work on tickets it hasn't seen before?" Four properties make that claim honest:

- **Held-out split** — eval examples must come from data the system under test never touched during
  training/indexing. If a retrieval system is graded on documents that are *already in its own
  index*, "great retrieval" partly just means "found the exact row it was given" — not "found relevant
  context for a new query." This is **leakage**, and it silently inflates every downstream metric.
- **Stratification** — random sampling from a skewed corpus (e.g. mostly "low priority / Technical
  Support" tickets) yields an eval set that's mostly one label, so an evaluator can look great by
  memorizing the majority class. Stratified sampling (fixed proportions per `(queue, priority)`
  stratum) forces the eval set to actually exercise every label combination.
- **Edge cases** — hand-authored examples that probe *graceful handling* (empty input, ambiguous
  wording, multiple issues in one ticket, near-max-length input) rather than label accuracy. Random
  sampling from real data rarely surfaces these deliberately; you have to write them by hand.
- **Inputs vs. reference outputs, and versioning** — every example is `{"inputs": {...}, "outputs":
  {...}}` (or `reference_outputs`, LangSmith's newer naming) — inputs are what the target receives,
  reference outputs are the ground truth an evaluator scores against, and they must never overlap in
  meaning (an evaluator that peeks at `inputs` for the answer isn't testing anything). The whole set is
  versioned (a name + version tag) so a metric change is comparable to *the same* dataset later, not a
  silently-different one.

## 2. In QueuePilot

- **The real split** — `eval/dataset.py::build_eval_dataset` calls `data/ingest.py`'s indexing
  boundary: `data/ingest.py` only embeds and writes `all_records[:CORPUS_CAP]` to Pinecone
  (`CORPUS_CAP` = 3000, the first English rows in CSV order — see
  `docs/final-build-plan/07-DATASET.md`). Everything from index `CORPUS_CAP` onward — roughly 13k
  English rows — was **never embedded**, so `build_eval_dataset` samples exclusively from
  `records[cap:]` (`held_out_records`), which is provably safe.
- **Stratified sampling** — `eval/dataset.py::_stratified_sample` groups the held-out pool by
  `(queue, priority)`, allocates proportionally per stratum with a seeded `random.Random`
  (`EvalSettings.seed`, `eval/settings.py`), and trims/tops-up deterministically to hit
  `sample_size` (`EvalSettings.sample_size`, default 160) exactly.
- **Edge cases** — `eval/fixtures.py::EDGE_CASES`: near-empty, ambiguous, multi-issue, and
  near-`max_input_chars` examples, each with `outputs={}` (no reference label) so exact-match
  evaluators return `None` (skip) rather than scoring them wrong — they're graded by the LLM-as-judge
  or manual inspection instead.
- **The leakage assertion** — the money shot, right in `build_eval_dataset`:
  ```python
  indexed_ids = {r.id for r in indexed_records}
  leaked = [r.id for r in sampled if r.id in indexed_ids]
  assert not leaked, f"Leakage detected: ..."
  ```
  This isn't a comment or a convention — it's an assertion that fails loudly the moment `CORPUS_CAP`
  or CSV row ordering ever drifts out of sync with the indexed set.
- **Versioning** — `EvalSettings.dataset_name` (`"queuepilot-eval"`) + `dataset_version` (`"v1"`,
  `eval/settings.py`); `eval/upload.py` idempotently creates the LangSmith dataset and adds only
  missing examples (keyed by input hash) so re-running the builder never duplicates rows.

## 3. Why this way

- **Why post-cap split instead of a separate random holdout carved out before indexing?** The design
  doc (`docs/final-build-plan/11-SLICE-D-DESIGN.md`) considered a seeded random split but rejected it
  — it would force re-indexing the whole corpus to guarantee the eval rows were excluded. The post-cap
  tail already exists, is large (~13k rows), and is *structurally* excluded by the same cap the
  indexer already respects — no extra work, no re-index, same guarantee
  (`05-DECISIONS-LOCKED.md → D15`).
- **Why assert leakage instead of trusting the split?** Trusting the split by convention (`we sample
  from the tail, so it's fine`) is exactly the kind of assumption that silently breaks when someone
  changes `CORPUS_CAP`, re-orders the CSV, or re-runs the eval builder against a different raw file. An
  assertion turns a silent correctness bug into a loud, immediate failure at dataset-build time —
  before it can corrupt every metric downstream.
- **Why stratify by `(queue, priority)` and not just `queue`?** Both are the fields the deterministic
  evaluators score (`queue_match`, `priority_match`) and both are logically independent (a "Billing"
  ticket can be low or high priority) — stratifying on just one axis would still let the eval set
  under-represent, e.g., high-priority Billing tickets specifically.
- **Why hand-author edge cases instead of relying on the sample to include some naturally?** Nothing
  guarantees a random or even stratified sample includes a near-empty ticket or one near the input
  size limit — those are rare by construction (real users don't usually submit near-max-length
  tickets), so the only reliable way to test graceful degradation on them is to write them by hand.

## 4. Verify it yourself

```bash
uv run python learn/12_eval_datasets.py
```

**Expected:** No CSV, no network. The script builds 50 synthetic records in memory, splits them at a
mini `CAP` (mirroring `records[:CORPUS_CAP]` / `records[CORPUS_CAP:]`), stratified-samples from the
held-out half using the same allocate-per-stratum algorithm as `eval/dataset.py::_stratified_sample`,
injects two real `eval.fixtures.EDGE_CASES` ids, and then runs the leakage check: `assert not
(eval_set_ids & indexed_ids)`, printing `PASSED` — plus, for contrast, what the same check would print
if a leak *had* occurred (without actually introducing one into the real eval set).

## 5. Self-quiz

1. Why does the leakage assertion compare **ids**, not the raw ticket **text**? What kind of leakage
   would an id-only check miss that a text-similarity check might catch — and why is QueuePilot's
   design (deterministic content-hash ids, per `docs/learn/_infra-A7-ingest.md`) enough to make that
   gap acceptable?
2. `eval/dataset.py::_stratified_sample` uses `random.Random(seed)` instead of the module-level
   `random` functions. Why does that specific choice matter for the versioning property described
   above?
3. `EDGE_CASES` examples carry `outputs={}`. Walk through what `queue_match(inputs, outputs,
   reference_outputs={})` returns for one of them, and explain why that's the *correct* behavior
   rather than a bug.

<details><summary>Answers</summary>

1. An id-only check misses **near-duplicate leakage** — a held-out ticket that's nearly identical in
   wording to an indexed one (e.g. a templated auto-reply) but has a different id, which a text/
   embedding-similarity check could catch but a plain id-set intersection cannot. QueuePilot's
   ingest uses deterministic **content-hash** ids (`docs/learn/_infra-A7-ingest.md`) — an id
   collision *is* a content collision — so genuinely identical rows are already caught by the id
   check; only near-duplicates (paraphrases, templates) slip through, and that's an accepted,
   documented gap rather than a silent one.
2. `random.Random(seed)` creates an isolated RNG instance whose sequence depends only on `seed`, not
   on how much other code has consumed from the shared global `random` state earlier in the process.
   If `_stratified_sample` used the global `random.shuffle`/`random.sample` instead, the exact sample
   produced would depend on *what else ran before it in the same process* — making "dataset v1" not
   reproducible from a bare seed, which breaks the versioning guarantee (same seed + same pool must
   always yield the same sampled ids).
3. `_field_match_evaluator` reads `reference_outputs.get(field)`; for an edge case, `reference_outputs
   == {}`, so `reference_value` is `None`/falsy, and the function returns `None` immediately — before
   comparing anything. This is correct: an edge case has no ground-truth queue (it exists to test
   graceful handling, not classification accuracy), so scoring it 0.0 would unfairly penalize the
   pipeline for "getting a label wrong" that was never defined; `None` tells `evaluate()` to skip it
   entirely rather than count it against the aggregate.

</details>

## 6. Takeaway

"A held-out split only earns the word 'held-out' when leakage is checked by assertion, not assumed by
convention — QueuePilot samples strictly from records beyond the indexing cap, stratifies by label so
every class is exercised, hand-injects edge cases that random sampling would rarely surface, and
fails loudly the instant an id from the eval set turns up in the indexed set."
