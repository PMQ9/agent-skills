---
name: postgresql
description: PostgreSQL-specific features, performance tuning, indexing, query analysis, and operational practices. Use whenever the user is working with Postgres specifically — writing complex queries, debugging EXPLAIN output, choosing index types, configuring connection pools, designing JSONB columns, partitioning tables, setting up replication, or operating Postgres in production. Triggers on "postgres," "psql," "pgsql," "EXPLAIN," "JSONB," "GIN," "pg_stat," "pgbouncer," "vacuum," "WAL," and any query-tuning question.
---

# PostgreSQL

This skill assumes general database design competence (see the `database-design` skill) and focuses on what's specifically Postgres. Unless noted, advice targets Postgres 14+; many features mentioned arrived in 14, 15, 16, or 17.

## What Postgres is exceptionally good at

It's worth saying out loud: Postgres in 2026 is the right default datastore for almost every backend system. It does:

- ACID transactions with strong isolation guarantees.
- JSONB with indexing, querying, and partial updates — covers most "I want a document store" needs.
- Full-text search with stemming and ranking — covers most "I want Elasticsearch" needs up to several million rows.
- Vector search via pgvector — covers most embedding-similarity needs up to tens of millions of vectors.
- Geospatial via PostGIS — best-in-class.
- Time-series via partitioning + BRIN indexes (or TimescaleDB) — covers most metrics-style workloads.
- Background jobs via `LISTEN/NOTIFY`, `SELECT ... FOR UPDATE SKIP LOCKED`, or pg_cron — covers most queue needs.
- Logical replication, foreign data wrappers, materialized views, recursive CTEs.

Most architectures with five datastores can be Postgres + one cache. Resist datastore proliferation until you have evidence.

## Connection management

This is where most production Postgres incidents start.

Postgres uses a process-per-connection model. Each connection costs ~10MB of RAM and a process slot. Connections are not free.

- **Set `max_connections` modestly** — 100–300 for most setups. Going higher without a pooler causes scheduler thrashing and OOMs.
- **Always pool connections.** Two real options:
  - **PgBouncer** (transaction mode for app workloads, session mode if you need session-scoped state like advisory locks across statements). Battle-tested, single-binary, low overhead.
  - **Application-level pool** (e.g., SQLAlchemy pool, node-postgres pool, HikariCP). Fine for a single instance; doesn't help when you scale out 50 app pods.
- **For serverless / many app instances → PgBouncer in front of Postgres.** Each app instance opens a small pool to PgBouncer; PgBouncer keeps a tight pool to Postgres.
- **Transaction-mode pooling has constraints.** No session-scoped features: no `SET` outside of transactions, no `LISTEN`, no prepared statements that span transactions, no temp tables that persist between calls. Most ORMs handle this fine if configured for transaction-mode pooling. Make sure prepared-statement caching is off or scoped per-transaction.

Connection-pool-saturation symptoms: requests queue, p99 latency cliffs, "remaining connection slots are reserved" errors. Watch `pg_stat_activity` count and active vs idle.

## Index types — when to use which

Postgres has six built-in index access methods. Most code uses one. Know the others.

### B-tree (default)
Equality and range queries on ordered data. Used by `CREATE INDEX` when you don't specify a method. Default for ~90% of indexes. Supports `=`, `<`, `>`, `BETWEEN`, `IN`, `LIKE 'prefix%'`, `ORDER BY`.

### GIN (Generalized Inverted Index)
For "many values per row" data: `JSONB`, arrays, full-text search (`tsvector`), trigrams (`pg_trgm`). Slower writes than B-tree, very fast lookups for containment and existence.

```sql
CREATE INDEX ON documents USING gin (tags);
CREATE INDEX ON documents USING gin (metadata jsonb_path_ops);  -- smaller, faster for @> queries
CREATE INDEX ON articles USING gin (to_tsvector('english', body));
CREATE INDEX ON users USING gin (email gin_trgm_ops);  -- fuzzy email matching
```

`jsonb_path_ops` is worth knowing: smaller and faster than the default `jsonb_ops`, but only supports `@>`. For most JSONB query patterns it's the right choice.

### GiST (Generalized Search Tree)
For "is this near / overlapping / containing" — geometric types, ranges, and full-text. Use for PostGIS, range types (`tstzrange`, `int4range`), and trigram fuzzy matching when you also need ranking.

```sql
CREATE INDEX ON bookings USING gist (room_id, period);  -- where period is tstzrange
CREATE INDEX ON locations USING gist (geom);  -- PostGIS geometry
```

### BRIN (Block Range Index)
Tiny index. Stores summary info per block range. Useful only when the column's values are physically correlated with insertion order — typically time-series data inserted in chronological order. A BRIN index on `created_at` for a billion-row append-only log is dramatically smaller than a B-tree and often plenty fast.

```sql
CREATE INDEX ON events USING brin (created_at);
```

If your table is heavily updated or rows arrive out of order, BRIN's effectiveness collapses. It's a "right tool, narrow job" index.

### Hash
Equality only, no ordering. In Postgres 10+ it's WAL-logged and crash-safe. Marginal benefit over B-tree in most cases — B-tree handles equality fine. Skip unless you've specifically measured a win.

### SP-GiST
Specialized partitioned trees — quad-trees, kd-trees. Niche; you'll know if you need it.

### Special index features

**Partial indexes** — index only rows matching a predicate.

```sql
CREATE INDEX ON jobs (created_at) WHERE status = 'pending';
CREATE UNIQUE INDEX ON users (email) WHERE deleted_at IS NULL;
```

The second one is the right way to do soft-deleted unique constraints.

**Expression indexes** — index a function of a column.

```sql
CREATE INDEX ON users (lower(email));  -- supports WHERE lower(email) = ?
CREATE INDEX ON events ((metadata->>'tenant_id'));
```

**Covering / INCLUDE** — non-key columns in the index leaf, allowing index-only scans.

```sql
CREATE INDEX ON orders (customer_id, created_at) INCLUDE (status, total_cents);
```

**`CONCURRENTLY`** — build the index without blocking writes. Always use in production.

```sql
CREATE INDEX CONCURRENTLY ON large_table (column);
```

If a `CONCURRENTLY` build fails, you're left with an `INVALID` index — drop it explicitly and rebuild.

## EXPLAIN — reading query plans

`EXPLAIN ANALYZE` runs the query and reports actual rows + actual time. Read top-down from the outermost node.

What to look for:

- **`Seq Scan` on a large table** — full table scan. Usually wrong if you have a selective filter; you're missing an index or the planner doesn't think the index is worth it.
- **`Rows` actual vs planned wildly off** — stats are stale. Run `ANALYZE table_name;`. If consistently off after analyze, increase `default_statistics_target` for the column.
- **`Nested Loop` with high iteration count** — fine for small inner sets, catastrophic if inner side is large. Often fixed by adding an index on the join column or by encouraging a hash join via better stats.
- **`Hash Join` or `Merge Join`** — usually appropriate for large joins.
- **`Filter:` removing many rows after a scan** — index isn't selective enough. Consider a partial index, a composite index, or rewriting the predicate.
- **`Sort` spilling to disk** (`Sort Method: external merge Disk: ...`) — increase `work_mem` or add an index that already provides the order.
- **`Bitmap Heap Scan`** — index lookup followed by random heap fetches. Often fine; if it's the bottleneck, a covering (`INCLUDE`) index can convert it to an index-only scan.
- **`Lossy heap blocks` in bitmap scans** — `work_mem` too small.

Always run `EXPLAIN (ANALYZE, BUFFERS)` — `BUFFERS` shows actual I/O. A query that's "fast" with a hot cache may be slow when cold. The buffer numbers tell you which.

For interactive plan exploration, paste output into a plan visualizer (e.g., explain.dalibo.com, pev2). Far easier than reading raw output.

## JSONB — when and how

JSONB is for genuinely schemaless or sparse data, or for "extension" fields the schema can't predict. It is not a substitute for designing a schema.

Use JSONB when:
- The shape varies legitimately by row (per-tenant custom fields, third-party API responses you don't control).
- The data is read mostly as a whole, occasionally queried by a path.
- You need to evolve the shape rapidly without migrations.

Don't use JSONB when:
- You query specific fields constantly — those should be columns.
- You join on the field — joins on `(metadata->>'foo')::int` work but are awkward.
- You enforce constraints across rows — CHECK constraints inside JSONB are painful.

### Operators worth knowing

- `->` returns JSONB; `->>` returns text. `column->'a'->>'b'` is "go into a, get b as text."
- `@>` containment: `data @> '{"status": "active"}'`. Excellent index target with GIN.
- `?` key existence: `data ? 'email'`.
- `jsonb_path_query`, `jsonb_path_exists` — JSONPath queries.
- `jsonb_set`, `jsonb_insert` — partial updates without round-tripping the whole document.

```sql
-- Index for containment queries
CREATE INDEX ON events USING gin (payload jsonb_path_ops);

-- Query
SELECT * FROM events WHERE payload @> '{"event_type": "login"}';

-- Index a specific path you query often
CREATE INDEX ON events ((payload->>'tenant_id'));
SELECT * FROM events WHERE payload->>'tenant_id' = '123';
```

A pragmatic pattern: **structured columns for the fields you always query, JSONB for the bag of "everything else."**

## Full-text search

Postgres FTS is excellent for "site search" up through millions of documents. Beyond that, dedicated engines start winning, but the threshold is higher than most teams assume.

```sql
-- Generated tsvector column kept in sync automatically
ALTER TABLE articles ADD COLUMN search tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body,  '')), 'B')
  ) STORED;

CREATE INDEX articles_search_idx ON articles USING gin (search);

-- Query
SELECT id, title, ts_rank(search, q) AS rank
FROM articles, plainto_tsquery('english', 'database design') q
WHERE search @@ q
ORDER BY rank DESC
LIMIT 20;
```

For "did you mean" / typo tolerance, combine with `pg_trgm`:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ON products USING gin (name gin_trgm_ops);

SELECT * FROM products WHERE name % 'aplie';  -- finds 'apple'
SELECT * FROM products ORDER BY name <-> 'aplie' LIMIT 10;  -- closest first
```

For semantic search, see the `pgvector-embeddings` skill — and consider hybrid (FTS + vector) before going full-vector.

## Common Table Expressions (CTEs) and window functions

`WITH` clauses make complex queries readable. As of Postgres 12, they are no longer optimization fences by default — the planner can inline them — so use them freely.

```sql
WITH recent_orders AS (
  SELECT customer_id, SUM(total_cents) AS spent
  FROM orders
  WHERE created_at > now() - interval '30 days'
  GROUP BY customer_id
)
SELECT c.id, c.name, ro.spent
FROM customers c
JOIN recent_orders ro ON ro.customer_id = c.id
ORDER BY ro.spent DESC
LIMIT 10;
```

**Recursive CTEs** for trees and graphs:

```sql
WITH RECURSIVE org_tree AS (
  SELECT id, name, manager_id, 0 AS depth
  FROM employees
  WHERE manager_id IS NULL

  UNION ALL

  SELECT e.id, e.name, e.manager_id, ot.depth + 1
  FROM employees e
  JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree ORDER BY depth, name;
```

**Window functions** for "per-group rank/lag/lead/running-total" without self-joins:

```sql
SELECT
  user_id,
  created_at,
  amount,
  SUM(amount) OVER (PARTITION BY user_id ORDER BY created_at) AS running_total,
  ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS recency_rank
FROM transactions;
```

Memorize these — they replace huge swaths of application-side aggregation logic.

## UPSERT and conflict handling

```sql
INSERT INTO users (id, email, name)
VALUES ($1, $2, $3)
ON CONFLICT (id) DO UPDATE
  SET email = EXCLUDED.email,
      name  = EXCLUDED.name,
      updated_at = now()
RETURNING *;
```

`EXCLUDED` is the row you tried to insert. Use `DO NOTHING` to skip duplicates, `DO UPDATE` to merge.

For "insert if not exists, return the row regardless," `INSERT ... ON CONFLICT DO NOTHING RETURNING ...` returns nothing on conflict — you have to follow with a SELECT, or use `DO UPDATE SET id = EXCLUDED.id` as a no-op trick that triggers RETURNING.

## Locking and concurrency

### Row-level locking
- `SELECT ... FOR UPDATE` — exclusive lock on rows you read; other readers can still read, but other writers wait.
- `SELECT ... FOR UPDATE SKIP LOCKED` — skip rows already locked. The basis of Postgres-as-a-queue.
- `SELECT ... FOR SHARE` — shared lock, prevents others from updating until you commit.

### Advisory locks
Application-level locks keyed by integer. Use for "only one process should run this job at a time" patterns.

```sql
SELECT pg_try_advisory_lock(12345);  -- non-blocking
SELECT pg_advisory_xact_lock(12345); -- released at end of transaction
```

### Postgres as a queue

```sql
-- Worker picks up a batch
WITH next_jobs AS (
  SELECT id FROM jobs
  WHERE status = 'pending' AND run_after <= now()
  ORDER BY run_after
  LIMIT 10
  FOR UPDATE SKIP LOCKED
)
UPDATE jobs
SET status = 'processing', locked_at = now(), worker_id = $1
FROM next_jobs
WHERE jobs.id = next_jobs.id
RETURNING jobs.*;
```

This pattern handles thousands of jobs/second comfortably. For very high throughput you eventually want a real queue, but "Postgres queue" gets most teams much further than expected. (Tools: pg-boss for Node, pgmq, river, oban, GoodJob, that family.)

## Partitioning

Native declarative partitioning works well for tables that grow forever (logs, events, time-series).

```sql
CREATE TABLE events (
  id BIGSERIAL,
  occurred_at TIMESTAMPTZ NOT NULL,
  user_id UUID NOT NULL,
  payload JSONB,
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE events_2026_01 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

Benefits: dropping old data is `DROP TABLE events_2024_01` (instant, no bloat); queries with the partition key prune to a subset of partitions.

Constraints:
- The partition key must be in the primary key.
- Use a tool to auto-create future partitions (pg_partman is the standard).
- Foreign keys *to* a partitioned table work in modern Postgres but require care.

Partition when a table is heading north of ~100M rows and has a natural time or tenant axis. Below that, plain indexes are fine.

## Vacuum, bloat, MVCC

Postgres uses MVCC: updates write new row versions; old versions become "dead tuples" until VACUUM cleans them up. Autovacuum runs in the background.

Symptoms of vacuum issues:
- **Table bloat** — table size much larger than live data. Sequential scans get slow.
- **Index bloat** — same, on indexes.
- **Long-running transactions block vacuum** — a session that's been idle in transaction for hours prevents cleanup of every dead tuple created since it started. **The single most common cause of mysterious bloat.** Hunt these down via `pg_stat_activity` (`state = 'idle in transaction'`).
- **Transaction ID wraparound** — at extreme scale or with vacuum disabled, you get the dreaded "must vacuum to prevent wraparound." Don't disable autovacuum.

Tuning autovacuum: usually you raise `autovacuum_max_workers` (3 → 6) and lower `autovacuum_vacuum_scale_factor` (0.2 → 0.05) for large tables that update frequently. Per-table settings via `ALTER TABLE ... SET (autovacuum_vacuum_scale_factor = 0.01)`.

## Replication and HA

- **Streaming replication** — physical, byte-level WAL streaming to one or more replicas. Replicas can serve read-only queries (small lag) and are promoted on primary failure. Default for HA.
- **Logical replication** — row-level changes published per table. Use for: cross-version upgrades, partial replication, fan-out to other systems, change data capture (CDC). Doesn't replicate DDL — schema changes require coordination.
- **Read replicas for read scaling** — works well if your reads tolerate <1s lag. Anti-pattern: routing reads of "what I just wrote" to a replica — race condition.

For managed Postgres (RDS, Cloud SQL, Neon, Supabase, Crunchy, etc.), most of this is automated. Know what your provider's RPO/RTO actually are — read the docs, don't assume.

## Backups

Two distinct things, both required:

1. **Logical backups** — `pg_dump` produces a SQL or custom-format archive, restorable on any version of Postgres ≥ source. Slow on large DBs but maximally portable. Run regularly; verify by restoring to a scratch instance.
2. **Physical / PITR (Point-in-Time Recovery)** — base backup + continuous WAL archiving. Lets you restore to any moment within retention. This is the real backup for a production DB.

If your provider claims "automated backups," ask: (a) what's the RPO, (b) have we tested restoring, (c) are they geographically replicated. Untested backups don't exist.

## Useful catalog queries

```sql
-- Slow queries (requires pg_stat_statements)
SELECT query, calls, total_exec_time, mean_exec_time, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Table sizes including indexes/toast
SELECT
  relname,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS total,
  pg_size_pretty(pg_relation_size(c.oid)) AS table_only,
  pg_size_pretty(pg_indexes_size(c.oid)) AS indexes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = 'public'
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 20;

-- Unused indexes (low scan count and big)
SELECT
  schemaname, relname, indexrelname,
  idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
JOIN pg_index USING (indexrelid)
WHERE NOT indisunique
  AND idx_scan < 50
  AND pg_relation_size(indexrelid) > 5 * 1024 * 1024
ORDER BY pg_relation_size(indexrelid) DESC;

-- Duplicate indexes
SELECT pg_size_pretty(SUM(pg_relation_size(idx))::bigint) AS size,
       (array_agg(idx))[1] AS idx1, (array_agg(idx))[2] AS idx2
FROM (
  SELECT indexrelid::regclass AS idx,
         (indrelid::text || E'\n' || indclass::text || E'\n' ||
          indkey::text || E'\n' || coalesce(indexprs::text, '')||E'\n' ||
          coalesce(indpred::text, '')) AS key
  FROM pg_index
) sub
GROUP BY key HAVING count(*) > 1;

-- Long-running queries / idle in transaction (the bloat-causers)
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state IN ('active', 'idle in transaction')
  AND now() - xact_start > interval '1 minute'
ORDER BY duration DESC;

-- Lock waits
SELECT
  blocked.pid     AS blocked_pid,
  blocked.query   AS blocked_query,
  blocking.pid    AS blocking_pid,
  blocking.query  AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));
```

Enable `pg_stat_statements` early — it's free and indispensable.

## Configuration knobs that matter most

For a server with N GB of RAM dedicated to Postgres:

- `shared_buffers` ≈ 25% of RAM.
- `effective_cache_size` ≈ 50–75% of RAM (a hint to the planner about OS cache).
- `work_mem` — per-operation; tune up if you see disk sorts. Start ~16–64MB; remember it can multiply by concurrent operations.
- `maintenance_work_mem` ≈ 1–2 GB for big indexes/vacuums.
- `max_wal_size` — bigger reduces checkpoint frequency (smoother latency); start ~4–8 GB.
- `random_page_cost` = 1.1 on SSD (default 4.0 assumes spinning disk and lies).
- `effective_io_concurrency` — 200+ on SSD.
- `default_statistics_target` — 100 default; raise to 500 or 1000 for tables with skewed data.

On managed Postgres, most of these are pre-tuned. On self-hosted, tools like PGTune give a reasonable starting point.

## Extensions worth knowing

- `pg_stat_statements` — query stats. Enable always.
- `pg_trgm` — trigram fuzzy matching.
- `pgcrypto` — `gen_random_uuid()` (now built-in in PG 13+) and crypto primitives.
- `uuid-ossp` — older UUID generators (`gen_random_uuid()` from pgcrypto/built-in is preferred now).
- `pgvector` — vector similarity search (see dedicated skill).
- `postgis` — geospatial.
- `timescaledb` — time-series superpowers (managed by Timescale, OSS core).
- `pg_partman` — partition automation.
- `pg_cron` — cron inside Postgres.
- `hypopg` — hypothetical indexes for "would this index help?" experiments.
- `pgaudit` — audit logging for compliance.

## Things to never do

- **Run `SELECT *` in production code.** Lock the column list. Adding a column shouldn't change application behavior unexpectedly.
- **Use `NOT IN (subquery)` with NULLable columns.** It silently returns wrong results when the subquery contains NULL. Use `NOT EXISTS`.
- **Disable autovacuum globally.** Tune it instead.
- **`UPDATE` without `WHERE`** — and yes, set `\set ON_ERROR_ROLLBACK interactive` and `\set AUTOCOMMIT off` in your `psqlrc` so you can `ROLLBACK` after the inevitable mistake.
- **Run schema changes during peak traffic** unless you've verified each statement's lock footprint.
- **Trust default `max_connections`** in production — pool.
- **Store secrets in plain text columns** — use a real secret manager or at least pgcrypto.
- **Keep `idle in transaction` sessions open.** Bloat killer.
- **Use `serial` / `bigserial` for new tables in PG 10+.** Use `GENERATED ALWAYS AS IDENTITY` — it's the SQL standard and avoids sequence-ownership weirdness.