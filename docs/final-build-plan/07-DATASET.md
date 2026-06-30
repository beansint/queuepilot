# 07 — Dataset (provenance, license, schema, handling)

## Source
- **Name:** Customer IT Support — Multilingual Ticket Dataset
- **Author:** tobiasbueck (Kaggle)
- **URL:** https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets
- **Why this dataset:** real-ish support tickets that ship *both* free text and operational labels
  (queue, priority, type) plus agent answers — so it serves as a retrieval corpus AND a benchmark for
  QueuePilot's outputs.

## License — ⚠ confirm before the repo goes public
Verify the exact license on the Kaggle page before flipping `queuepilot` public (end of Slice A).
Regardless of license, **we do not commit the raw data** — only this documentation + a reproducible
download script. `data/raw/` and `*.csv` are gitignored.

## How to obtain it (reproducible)
1. Get a Kaggle API token: https://www.kaggle.com/settings → API → **Create New Token**
   (downloads `kaggle.json` containing `username` + `key`).
2. Put them in `.env`: `KAGGLE_USERNAME=...`, `KAGGLE_KEY=...` (or place `~/.kaggle/kaggle.json`).
3. Run: `uv run python data/download.py` → copies the CSV(s) into `data/raw/`.

Fallback (no API): download the zip from the dataset page, unzip, and drop the CSV(s) into `data/raw/`.

## Schema — confirmed at ingest, isolated in `data/normalize.py`
The dataset ships multiple CSV "version" files and a multilingual set of columns. The exact column
names are **confirmed against the downloaded CSV during A7** and mapped in one place
(`data/normalize.py`) so a schema change touches a single file. Expected fields (to verify on download):
text subject + body, an agent `answer`, and labels for `type`, `queue`, `priority`, plus a `language`
column and several `tag` columns.

→ See `02-DATA-MODEL.md` for the normalized `TicketRecord` shape we map into.

## Our handling (v1)
- **Language filter:** keep **English** only (BM25 is fit for English; `02-DATA-MODEL.md`).
- **Field mapping:** `subject + body → text`; keep `queue`, `priority`, `type`; `answer → reply corpus`
  (kept for later slices).
- **Cap:** `CORPUS_CAP` (default **3000**) to control embedding cost / stay in Pinecone free tier.
- **Honesty:** ingest logs `indexed=N, dropped=M (reasons)` — never silently truncate.

## Derived artifacts (these, not the raw CSV, are the system state)
- The Pinecone `queuepilot` index (dense + sparse vectors + metadata).
- `data/artifacts/bm25_params.json` — the fitted BM25 vocabulary (query-time encoding).
