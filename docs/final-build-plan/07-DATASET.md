# 07 — Dataset (provenance, license, schema, handling)

## Source
- **Name:** Customer IT Support — Multilingual Ticket Dataset
- **Author:** tobiasbueck (Kaggle)
- **URL:** https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets
- **Why this dataset:** real-ish support tickets that ship *both* free text and operational labels
  (queue, priority, type) plus agent answers — so it serves as a retrieval corpus AND a benchmark for
  QueuePilot's outputs.

## License — CC BY 4.0 (confirmed)
**Attribution 4.0 International (CC BY 4.0)** — free to use and redistribute *with attribution*.
Safe for the public portfolio repo. We still **do not commit the raw data** — only this documentation
+ a reproducible download script (`data/raw/` and `*.csv` are gitignored).

**Required attribution** (keep in README + this doc):
> "Customer IT Support — Multilingual Ticket Dataset" by tobiasbueck (Kaggle), licensed under
> CC BY 4.0. https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets

## How to obtain it (reproducible)
1. Get a Kaggle API token: https://www.kaggle.com/settings → API → **Create New Token**
   (downloads `kaggle.json` containing `username` + `key`).
2. Put them in `.env`: `KAGGLE_USERNAME=...`, `KAGGLE_KEY=...` (or place `~/.kaggle/kaggle.json`).
3. Run: `uv run python data/download.py` → copies the CSV(s) into `data/raw/`.

Fallback (no API): download the zip from the dataset page, unzip, and drop the CSV(s) into `data/raw/`.

## Schema — CONFIRMED (2026-06-30)
The download ships 5 CSVs. **Primary source: `aa_dataset-tickets-multi-lang-5-2-50-version.csv`**
(28,587 rows; most English content). Columns (16):

```
subject, body, answer, type, queue, priority, language, version, tag_1 .. tag_8
```
(The `dataset-tickets-multi-lang-4-20k.csv` is the same minus `version`, 20k rows; German-only
normalized files are ignored for v1.)

- **language:** `en` (16,338) / `de` (12,249) → v1 keeps **en** only.
- **queue** (label) e.g. "Technical Support", "Customer Service".
- **priority** (label): `high` / `medium` / `low` (lowercase).
- **type** (label): e.g. "Incident", "Request".
- `tag_1..tag_8` are sparse free-text tags (often blank); not required for v1.

`data/normalize.py` isolates this mapping into the normalized `TicketRecord` (`02-DATA-MODEL.md`):
`subject + body → text`, keep `queue/priority/type`, `answer → reply corpus`, drop non-`en` rows.

## Our handling (v1)
- **Language filter:** keep **English** only (BM25 is fit for English; `02-DATA-MODEL.md`).
- **Field mapping:** `subject + body → text`; keep `queue`, `priority`, `type`; `answer → reply corpus`
  (kept for later slices).
- **Cap:** `CORPUS_CAP` (default **3000**) to control embedding cost / stay in Pinecone free tier.
- **Honesty:** ingest logs `indexed=N, dropped=M (reasons)` — never silently truncate.

## Derived artifacts (these, not the raw CSV, are the system state)
- The Pinecone `queuepilot` index (dense + sparse vectors + metadata).
- `data/artifacts/bm25_params.json` — the fitted BM25 vocabulary (query-time encoding).
