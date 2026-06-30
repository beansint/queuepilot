# Infra note (A7) — Kaggle ingest + normalize

> Infra note (not a numbered concept doc — NN 04/05 are reserved for A6 hybrid fusion and A8
> confidence). Task: `A7`. Code: `data/normalize.py`, `data/ingest.py`.

**What the ETL pipeline does here.** "ETL" (Extract, Transform, Load) names the three phases:
- **Extract** — `load_rows()` reads the Kaggle CSV with stdlib `csv.DictReader` (no pandas). One
  file, one function, zero external state.
- **Transform** — `normalize_rows()` applies business rules: keep English rows only, drop empty
  text, combine `subject + "\n\n" + body → text`, assign a stable id. The transformation is a
  pure function: given the same input stream it always produces the same output.
- **Load** — `ingest.py` embeds the normalized texts (Gemini), encodes sparse vectors (BM25), and
  upserts everything to Pinecone. The load step is the only one that touches external services.

Separating the three phases means the T step is unit-testable with no API keys and the E step is
swappable (if the dataset changes, only `normalize.py` needs to change).

**Why a deterministic content-hash id makes re-ingest idempotent.** Each record's id is
`"t_" + sha1(subject + "\n" + body).hexdigest()[:16]`. Because sha1 is a pure function of the
content, the same ticket always gets the same id. Pinecone's `upsert` operation is an upsert
(insert-or-replace), so running the ingest twice writes the same vector at the same id — no
duplicates, no extra costs. This is particularly important when the API goes down mid-ingest:
just re-run from the beginning and only the missing records are effectively added. Without
content-addressing, you'd get duplicate vectors with different ids.

**Why BM25 is fit on the SAME capped corpus we embed.** BM25 builds a vocabulary from the
documents you give it: every unique token gets an integer index and an IDF weight. At query time,
`encode_query()` maps query tokens onto those same integer indices. If BM25 were fit on the full
28k corpus but we only embedded and upserted 3k, the sparse vectors in Pinecone would reference
a vocabulary computed over unseen documents — weights would be miscalibrated. Fitting BM25 on
exactly the capped set ensures the stored sparse vectors and the query-time encoder share the
same vocabulary. This is why `encoder.save()` runs immediately after `encoder.fit(capped_texts)`
and before any upsert.

**Why embedding is batched.** The Gemini embedding API accepts a list of `contents` per call but
has a per-call limit (~100 texts). Batching in `ingest.py` chunks the `texts` list into slices of
100 and calls `embed_documents` once per slice, concatenating the results. This is cheaper than
100 individual API calls (fewer round-trips) and safe within the API's per-call content limit.
Batching also makes progress reporting straightforward: print a counter after each batch.

**Self-check:** Why does fitting BM25 on the full 28k corpus (rather than the capped 3k) produce
misaligned sparse vectors at query time? What property of `sha1(subject + "\n" + body)` guarantees
that running the ingest twice never creates duplicate Pinecone vectors? Why does `ingest.py` cap
records *before* fitting BM25, rather than fitting on all English rows first?
