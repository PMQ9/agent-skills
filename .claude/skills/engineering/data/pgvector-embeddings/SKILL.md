---
name: pgvector-embeddings
description: Vector similarity search and AI embedding pipelines with pgvector — schema design, index choice (HNSW vs IVFFlat), distance operators, chunking strategies, hybrid search (vector + full-text + keyword), RAG patterns, scaling considerations, and when to graduate to a dedicated vector DB. Use whenever the user is building semantic search, RAG (retrieval-augmented generation), recommendation systems, embedding-based deduplication, or any feature that involves storing and querying vectors. Triggers on "embedding," "embeddings," "vector," "pgvector," "RAG," "semantic search," "similarity search," "OpenAI embeddings," "Cohere embeddings," "sentence-transformers," and any "find similar X" question.
---

# pgvector & AI Embeddings

Production patterns for building embedding-powered features on Postgres. Targets pgvector ≥ 0.7 (HNSW with iterative scan, halfvec, sparsevec).

## When pgvector is the right choice

**Use pgvector when:**
- You have ≤ ~50M vectors and want to run vector queries alongside relational data (the same `WHERE tenant_id = ?` that filters rows should filter the vector search).
- You want one operational story: one DB to back up, monitor, secure.
- You're doing RAG, semantic search, dedup, recommendations on a "normal" SaaS scale.

**Consider a dedicated vector DB (Qdrant, Pinecone, Weaviate, Milvus, Vespa, Turbopuffer) when:**
- You're past ~50M vectors with strict p99 latency requirements.
- You need advanced features pgvector doesn't ship: payload indexing optimizations, multi-vector per record, learned sparse retrieval, SPLADE, ColBERT-style late interaction, cluster autoscaling.
- The vector workload dominates your DB and is starving other queries of resources.

The crossover point keeps moving up — pgvector with HNSW handles tens of millions of vectors comfortably. Default to pgvector and earn the right to migrate.

## Setup and schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The basic table shape:

```sql
CREATE TABLE document_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  tenant_id   UUID NOT NULL,
  chunk_index INTEGER NOT NULL,
  content     TEXT NOT NULL,
  token_count INTEGER NOT NULL,
  embedding   vector(1536),         -- dimension matches the model
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);

CREATE INDEX ON document_chunks (tenant_id);
CREATE INDEX ON document_chunks (document_id);
```

Notes:
- **The `vector(N)` dimension is fixed at table creation.** Changing models means changing the column (or running both side by side during migration).
- **Store `tenant_id` and any other strong filters as columns**, not just in `metadata`. The query planner uses real columns; JSONB filters are slower.
- **Always store the source `content`** alongside the embedding. You'll need it to send to the LLM during retrieval, and you'll need it to re-embed when you change models.
- **Store `metadata` as JSONB** for flexible filters (source URL, page number, section title, language). Index specific paths if you filter by them frequently.

### Vector type variants (pgvector 0.7+)

| Type | Storage | Use case |
|---|---|---|
| `vector(N)` | 4 bytes/dim (float32) | Default. Use unless storage is a real problem. |
| `halfvec(N)` | 2 bytes/dim (float16) | Half the storage, ~negligible recall loss for most embedding models. Strong default for >10M vectors. |
| `bit(N)` | N bits | Binary embeddings (Cohere binary, Matryoshka quantization). Very fast Hamming distance, ~32x smaller. Use as a re-rank candidate generator. |
| `sparsevec(N)` | Variable | Sparse vectors (BM25, SPLADE). Use for learned sparse retrieval. |

For most apps starting out: `vector` (full precision) until storage hurts. Then `halfvec`. Then quantization patterns.

## Distance operators

pgvector exposes three operators. Match the operator to how the embedding model was trained:

| Operator | Distance | Use when |
|---|---|---|
| `<->` | L2 (Euclidean) | Rare for modern embeddings |
| `<=>` | Cosine distance | OpenAI, Cohere, most sentence transformers |
| `<#>` | Negative inner product | When embeddings are normalized; faster than cosine |

For OpenAI's `text-embedding-3-*`, Cohere's `embed-*`, and most sentence-transformers: **use cosine (`<=>`).**

If you normalize vectors to unit length at ingest (which OpenAI and Cohere already do), `<#>` (inner product) is mathematically equivalent to cosine and slightly faster. Most teams just use `<=>` and don't worry about it.

```sql
-- top-K nearest by cosine distance, with a metadata filter
SELECT id, content, 1 - (embedding <=> $1) AS similarity
FROM document_chunks
WHERE tenant_id = $2
ORDER BY embedding <=> $1
LIMIT 10;
```

`1 - distance` converts cosine distance ∈ [0, 2] into a similarity score ∈ [-1, 1]. Display similarity, sort by distance.

## Indexing — HNSW vs IVFFlat

pgvector ships two ANN (approximate nearest neighbor) index types. **Default to HNSW.**

### HNSW (Hierarchical Navigable Small World)

```sql
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

- **Build time:** Slower than IVFFlat (proportional to vector count × `m` × `ef_construction`).
- **Query time:** Excellent recall/latency trade-off; the standard for production.
- **Memory:** Higher than IVFFlat. For 10M × 1536d vectors, plan ~30 GB+ for the index in `shared_buffers` to be hot.
- **Inserts:** Supported online; new rows are findable immediately. Cost scales with `m` and `ef_construction`.
- **No training required.** You can build the index on an empty table and rows index incrementally.

Tune two parameters:
- **`m`** (build): edges per node. 16 is a strong default. Higher = better recall, more memory, slower builds.
- **`ef_construction`** (build): candidates considered while building. 64 is fine; raise to 128–200 for higher recall on demanding workloads.
- **`hnsw.ef_search`** (query, runtime): candidates considered per query. Default 40. **This is the recall/speed knob.** Raise to 80–200 for higher recall at the cost of latency.

```sql
SET hnsw.ef_search = 100;        -- per-session
SET LOCAL hnsw.ef_search = 100;  -- per-transaction
```

### IVFFlat

```sql
CREATE INDEX ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

- **Build time:** Faster than HNSW.
- **Query time:** Decent, but generally lags HNSW for the same recall.
- **Requires representative data at build time** — `lists` should be roughly `√N` for N rows. **You should build this index *after* loading data**, not on an empty table.
- **Inserts after build go to a "fallback" partition** — recall degrades over time as new data accumulates outside the trained centroids. You'll want to `REINDEX` periodically.

Use IVFFlat when: you have a static or rarely-updated corpus, and HNSW build time is prohibitive. Otherwise: HNSW.

### Filter-aware queries — the critical pattern

ANN indexes on the embedding alone work well for "top K over the whole table." They become tricky when you also have a `WHERE` clause. Two patterns:

**1. Filter-then-search** — small filtered set:
```sql
-- If the filter is highly selective, the planner uses the B-tree on tenant_id
-- and does an exact KNN over the matching rows. Fast and exact.
SELECT id, content
FROM document_chunks
WHERE tenant_id = $2
ORDER BY embedding <=> $1
LIMIT 10;
```

**2. ANN with `iterative_scan`** (pgvector 0.8+):
```sql
SET hnsw.iterative_scan = strict_order;
-- The HNSW scan continues until it has K results that satisfy the WHERE clause.
-- Works correctly with filters; tune ef_search higher to compensate.
```

For pre-0.8 pgvector, the standard workaround was a CTE that overshoots:

```sql
WITH candidates AS (
  SELECT id, content, embedding <=> $1 AS dist
  FROM document_chunks
  ORDER BY embedding <=> $1
  LIMIT 200                  -- overshoot
)
SELECT * FROM candidates
WHERE tenant_id = $2          -- post-filter
ORDER BY dist
LIMIT 10;
```

This works but loses results when the filter is highly selective relative to the overshoot. **If you're on 0.8+, prefer `iterative_scan`.**

### Partial indexes for hot subsets

If most queries hit one tenant or status:

```sql
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE tenant_id = '00000000-...';        -- one big tenant
```

Or for soft-deleted data:

```sql
CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE deleted_at IS NULL;
```

## Choosing an embedding model

Three considerations: **quality** (MTEB benchmark performance), **dimension** (storage and speed), and **cost** (per-token API or self-hosted GPU).

Reasonable defaults as of early 2026:

- **OpenAI `text-embedding-3-small`** (1536d, supports dimension reduction down to 256–512) — strong quality, cheap, easy. Default for most apps.
- **OpenAI `text-embedding-3-large`** (3072d, reducible) — higher quality, more expensive, larger storage.
- **Cohere `embed-v3` family** — multilingual, strong on retrieval-tuned tasks, supports input types (`search_document` vs `search_query`).
- **Voyage `voyage-3` family** — strong on the retrieval benchmark, good price.
- **Self-hosted: BGE / E5 / GTE / Nomic / Stella families** — good quality, runs on CPU or modest GPU. Use when data sensitivity or cost makes APIs untenable.

Notes:

- **Always use the same model for the index and the query.** A query embedded with model A finding chunks embedded with model B produces nonsense (similarity scores that aren't meaningful).
- **Some models distinguish query vs document.** OpenAI doesn't; Cohere and BGE do. Use the right input type or you'll lose recall.
- **Matryoshka / dimension truncation** (OpenAI 3-*, Nomic) — you can truncate the vector to a lower dimension at ingest with minor recall loss. 512d often gives 90%+ of 1536d quality at 1/3 the storage. Test on your data.
- **Plan for re-embedding.** Models improve. Build the pipeline assuming you'll re-embed everything at some point — keep raw text, version the model identifier, support running old + new in parallel during cutover.

## Chunking — the most underrated lever

Quality of retrieval depends more on chunking strategy than on the embedding model, in practice.

Default approach for prose documents:

1. **Split on natural boundaries** — sections, paragraphs — first.
2. **Pack into chunks of 512–1024 tokens** (model context for embedding is usually 8K, but smaller chunks retrieve more precisely).
3. **Overlap chunks by 10–20%** so a fact spanning a chunk boundary appears in both.
4. **Preserve hierarchical context.** Prepend the document title and section heading to each chunk's text, so an embedding of "the warranty period is 2 years" also contains "Acme Widget / Section 5: Warranty."

For code, split on functions/classes. For chat logs, split on turn boundaries. For tables, embed each row plus column headers as one chunk. **Don't split structured content character-naively** — it destroys signal.

Tools:
- `langchain` / `llama_index` text splitters (RecursiveCharacterTextSplitter is the workhorse).
- `unstructured` for parsing diverse file types into chunkable units.
- Custom parsers for your specific corpus — usually worth the effort.

Store the chunking parameters with the chunks (chunker version, chunk size, overlap) so you can detect old data when you tune.

## Hybrid search — almost always better than pure vector

Pure vector search misses exact matches: a query for "K8s 1.29" might pull "Kubernetes 1.28" if the embedding thinks they're synonymous. Pure keyword (BM25 / FTS) misses paraphrases. **Combine them.**

The standard recipe:

1. Run vector search → top-K candidates by similarity.
2. Run keyword search (Postgres FTS) → top-K candidates by BM25 / `ts_rank`.
3. **Reciprocal Rank Fusion (RRF)** to merge the two ranked lists.
4. (Optional) Re-rank top 20–50 with a cross-encoder (Cohere Rerank, BGE-reranker, Voyage Rerank).

```sql
-- Hybrid query in one round-trip using RRF
WITH vector_search AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS rank
  FROM document_chunks
  WHERE tenant_id = $3
  ORDER BY embedding <=> $1
  LIMIT 50
),
keyword_search AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(search_tsv, q) DESC) AS rank
  FROM document_chunks, plainto_tsquery('english', $2) q
  WHERE tenant_id = $3 AND search_tsv @@ q
  LIMIT 50
),
fused AS (
  SELECT id, SUM(1.0 / (60 + rank)) AS score
  FROM (
    SELECT id, rank FROM vector_search
    UNION ALL
    SELECT id, rank FROM keyword_search
  ) combined
  GROUP BY id
)
SELECT c.id, c.content, f.score
FROM fused f
JOIN document_chunks c USING (id)
ORDER BY f.score DESC
LIMIT 10;
```

The constant `60` is the RRF parameter `k` — a smoothing term, 60 is the original-paper default and works well. Tune only with measurement.

For full-text, add a generated `tsvector` column with a GIN index — see the `postgresql` skill for the pattern.

**Why this works:** vector similarity captures semantic meaning; BM25 captures lexical specificity (proper nouns, version numbers, acronyms). RRF fuses them without needing calibrated scores. A cross-encoder on top of fused candidates lifts quality further at the cost of latency.

## Re-ranking

Cross-encoders score (query, document) pairs directly — much better quality than bi-encoder embeddings, but too slow to apply to a million docs. Use them as a second stage:

1. Retrieve 50–100 candidates with vector / hybrid (cheap, fast).
2. Score each with a cross-encoder reranker (Cohere Rerank, Voyage Rerank, BGE-reranker, or a self-hosted MS Marco-trained model).
3. Return top 5–10 by reranker score.

Adds 100–500ms latency depending on candidate count and reranker. Often worth it for quality-critical use cases (RAG over enterprise docs, search results UX).

## RAG end-to-end

The full pattern that holds up in production:

```
[ingestion]
  document → parse → chunk → embed → INSERT INTO chunks (with metadata)

[query]
  user question
    → (optional) query rewriting (HyDE, multi-query, decomposition)
    → embed query
    → hybrid retrieval (vector + BM25 + filters)
    → rerank top N
    → assemble prompt with citations
    → LLM
    → return answer + citations
```

Pieces worth knowing:

- **Query rewriting / HyDE.** A short user query like "warranty?" embeds poorly. Generate a hypothetical answer (HyDE) and embed *that*. Or expand into 3–5 paraphrased queries (multi-query retrieval) and union the candidates. Adds a small LLM call but significantly lifts recall on terse queries.
- **Citations are non-negotiable.** Always send chunk IDs / source URLs alongside content; render citations in the response. Without them, hallucinations are invisible.
- **Filter by user / tenant in the SQL.** Never filter in the application after retrieval — that leaks data to the LLM and burns latency. Use `WHERE tenant_id = ?` (with RLS as a backstop).
- **Cache embeddings of stable queries.** A query embedding is identical for the same input string with the same model — cache aggressively in Redis or Postgres.
- **Chunk metadata in the prompt.** Including section heading, doc title, last-updated date in the chunk text helps the LLM's grounding.
- **Evaluation.** Build a small labelled set of (query, expected answer / expected source) pairs. Run nightly. Track recall@K, MRR, and answer correctness. This is the only way to know whether changes help.

## Performance and scaling

### Index memory

HNSW must be in RAM for fast queries. Estimate:

```
index_size ≈ N × (4 × dim + 8 × m × layer_factor) bytes
```

For 10M × 1536d × m=16: roughly 65 GB index. The index needs to fit in `shared_buffers` (or OS cache) for hot performance.

If RAM is limited:
- Use `halfvec` (halves storage and index size).
- Use Matryoshka truncation to a smaller dim (512d cuts storage by 3x).
- Partition by tenant or time (smaller per-partition indexes).
- Quantization patterns (binary embeddings as candidate generation).

### Throughput

Vector search is CPU-heavy on the database. A single Postgres instance handles **~hundreds to low thousands of vector queries/second** depending on hardware, dim, and ef_search. For higher QPS:

- **Read replicas** — vector queries are read-only; route them to replicas. Replication lag on inserts is tolerable for most RAG.
- **Pre-compute query embeddings** — cache popular queries.
- **Quantize** — binary or int8 quantization for the candidate stage; rerank top candidates with full-precision.
- **Graduate to a dedicated vector DB** if you've exhausted the above.

### Insert throughput

Bulk-load with `COPY` whenever possible. Build the HNSW index *after* loading initial data — incremental insert into HNSW is supported but slower per row than batch build. For very large initial loads, consider `lists`-style IVFFlat first, then a re-index to HNSW.

### Watch out for

- **Forgetting to vacuum.** Vector tables update like any other; bloat hurts. Standard autovacuum tuning applies.
- **Wrong distance op for the model.** Silently returns garbage. Check what the model emits.
- **Mixing models.** A single column with vectors from two models is broken. Track `embedding_model_version` per row, never mix in one query.
- **Storing only the embedding.** When you change models, you can't re-embed without the source text. Store the source.
- **Letting the embedding service rate-limit your ingestion.** Batch (most APIs accept 100–2048 inputs per call), queue, retry with exponential backoff.

## Evaluation — the part most teams skip

Build evaluation into the pipeline from day one:

- **Retrieval eval.** A set of (query → relevant doc IDs) pairs. Measure recall@K, MRR, NDCG. Run on every change.
- **Answer eval.** A set of (query → expected answer / key facts). Measure with LLM-as-judge for answer correctness, faithfulness (no hallucination), citation accuracy.
- **Track regressions.** A change that improves average quality but tanks one important query is a bad change.

Open-source frameworks: `ragas`, `deepeval`, `promptfoo`, plus your own per-domain rubric. The exact tool matters less than having one and running it on every PR that touches retrieval or prompts.

## Anti-patterns

- **Storing only `embedding` and `id`.** Now you can't filter, can't show context, can't re-embed.
- **Putting all filters in JSONB metadata.** Slow and the planner can't use B-trees.
- **Using IVFFlat on a constantly-growing table without periodic reindex.** Recall silently degrades.
- **Building HNSW on a tiny table (< ~10K rows).** Sequential scan beats it. Don't index until you need to.
- **Re-embedding on every query for the same string.** Cache.
- **Pure vector search where keywords matter.** Ship hybrid from day one — RRF is 30 lines of SQL.
- **Storing 1536-dim vectors when you could store 512-dim.** Test truncation; the storage savings are real and the recall loss is often < 1%.
- **One global vector table with no `tenant_id` column.** Slow filters, leak risk. Add the column and index it.
- **Trusting cosine similarity scores as absolute thresholds across models.** "0.85" means different things in different models. Use ranks or model-specific calibrated thresholds.
- **No re-embedding plan.** When the next-gen model lands and recall jumps 5pts, you'll want to migrate. Design for it from the start.