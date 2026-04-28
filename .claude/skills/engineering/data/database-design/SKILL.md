---
name: database-design
description: Schema design, normalization, indexing strategy, transaction reasoning, and migration discipline for relational databases. Use whenever the user is modeling data, designing tables, deciding what to index, debugging slow queries, choosing isolation levels, planning a migration, or asking how to represent something in a database. Triggers on "schema," "table," "model," "index," "foreign key," "migration," "transaction," "ER diagram," "normalize," "denormalize," and any "how do I store X" question.
---

# Database Design

Engine-agnostic guidance for designing relational schemas. For Postgres-specific features (JSONB, GIN indexes, partitioning, EXPLAIN tuning), use the `postgresql` skill alongside this one.

## The core mindset

**Schema is the contract.** It outlasts every framework, ORM, and rewrite that touches it. Design it deliberately. A clean schema makes the application easy; a dirty schema makes the application impossible.

**Design for the access patterns you have, not the OO model in your head.** The question is never "how would I model this in Java/Python/TypeScript." The question is "what are the queries, what are the writes, what must be atomic, and what must be consistent." The schema falls out of that.

**Constraints are documentation that the database enforces.** Foreign keys, NOT NULL, CHECK, UNIQUE — use all of them. The database is your last line of defense; your application code is not.

**Migrations are forever.** Every migration that has ever run in production is permanent in the audit history of your schema. Treat each one as a public commit message.

## Normalization — what to actually use

You don't need to recite the formal definitions. You need three rules:

1. **Each fact lives in exactly one place.** If a customer's email appears in three tables, two of them are stale and you don't know which.
2. **Each row of a table is about one thing.** A `users` table that has both individual user fields and "the team they admin" fields is two tables pretending to be one.
3. **No repeating groups in columns.** `tag1, tag2, tag3` columns are a bug. So is a comma-separated string. Use a related table or a proper array column (Postgres) — but not stringly-typed lists.

That's effectively 1NF/2NF/3NF for working purposes. Beyond 3NF (BCNF, 4NF, 5NF) is rarely worth memorizing — apply the rules above and you'll be fine.

### When to denormalize (deliberately)

Normalize first; denormalize when you have evidence. Legitimate reasons:

- **Read amplification** — a hot read path joins six tables every request and the join is the bottleneck. Cache the derived value as a column or materialized view.
- **Historical immutability** — an order's `unit_price_at_purchase` should be copied onto the order row, not joined to the products table, because the product price changes and the order's price must not.
- **Aggregates updated on write** — `comment_count` on a post, kept in sync via triggers or application code, when the alternative is a `COUNT(*)` on every page load.

For each denormalization, document **how it stays consistent** (trigger, scheduled job, application code) and **what happens when it drifts** (does it self-heal, or does someone need to run a backfill).

## Naming conventions

Pick one and apply it everywhere — consistency is worth more than which choice you made.

A reasonable default:

- Tables: plural snake_case nouns — `users`, `order_items`, `audit_events`.
- Columns: snake_case — `created_at`, `email_verified_at`.
- Primary key: `id`.
- Foreign keys: `<singular_table>_id` — `user_id`, `order_id`.
- Booleans: positive phrasing with a verb — `is_active`, `has_verified_email`, `is_deleted`. Avoid `disabled` (double negation in queries).
- Timestamps: `<event>_at` — `created_at`, `updated_at`, `deleted_at`, `published_at`. Always store timezone-aware (`TIMESTAMPTZ` in Postgres). Never store local time.
- Junction tables: `<table_a>_<table_b>` — `users_roles`, `posts_tags`.
- Indexes: `<table>_<columns>_idx` — `users_email_idx`. Unique: `<table>_<columns>_key`.

## Primary keys

Three reasonable choices, in order of preference for most apps:

1. **UUIDv7 (or ULID)** — sortable by time, globally unique, no coordination required, doesn't leak row counts. Excellent default for new systems. In Postgres, generate with `uuidv7()` (PG 18+) or a small extension.
2. **BIGINT identity** — smallest, fastest, simplest. Use when the system is a single tenant with one DB and you don't need to merge data across instances. Leaks row count via sequential IDs.
3. **UUIDv4** — random, no ordering, hurts B-tree insert locality at scale. Use only if v7/ULID is unavailable.

Avoid:
- **Natural keys as primary keys** — emails change, usernames change, "permanent" identifiers turn out not to be. Use a surrogate `id`, and put a `UNIQUE` constraint on the natural key.
- **Composite primary keys on regular tables** — fine on junction tables (`(user_id, role_id)` is correct), painful everywhere else because every FK pointing at you becomes composite too.

## Foreign keys and referential integrity

Always declare foreign keys. Yes, in production. The "ORM enforces this" argument is wrong; the ORM enforces it for code paths you control. The DB enforces it for everything — ad-hoc fixes, other services, the intern's one-off script.

Pick the `ON DELETE` behavior consciously:

- `RESTRICT` (default) — refuses deletion if children exist. Safe default for parent records you wouldn't actually delete.
- `CASCADE` — children deleted along with the parent. Use for ownership relationships (delete user → delete their sessions, OAuth tokens, notifications). Use when the child genuinely cannot exist without the parent.
- `SET NULL` — child's FK becomes NULL. Use when the relationship is informational (delete a category → posts remain but uncategorized).
- `NO ACTION` — like RESTRICT but checked at end of transaction. Rarely what you want.

**Always index your FK columns.** Postgres does not auto-index them, and joins/cascades on unindexed FKs become catastrophic at scale.

## Choosing column types

- **Strings**: `VARCHAR(n)` and `TEXT` are the same in Postgres — use `TEXT` and add a `CHECK (length(col) <= N)` if you need a bound.
- **Integers**: `INTEGER` for normal counts, `BIGINT` for IDs and anything that could plausibly exceed 2 billion (more often than you'd think).
- **Money**: `NUMERIC(precision, scale)` — never `FLOAT` or `DOUBLE`, ever, for anything financial. `NUMERIC(19, 4)` covers most fiat currency needs.
- **Booleans**: `BOOLEAN` — not `INT 0/1`, not `CHAR 'Y'/'N'`.
- **Timestamps**: `TIMESTAMPTZ`. Always. Stored as UTC, displayed in the user's timezone at the application layer.
- **Dates without time**: `DATE` — for birthdays, holidays, things that aren't moments.
- **Enums**: native `ENUM` types are awkward to evolve in Postgres (adding values requires care; removing requires recreate). Often a `TEXT` column with a `CHECK` constraint, or a small lookup table with FK, is more maintainable.
- **JSON**: `JSONB` (in Postgres) for genuinely schemaless or sparse data. Don't use it as a way to avoid columns for fields you query — that's just a slower table.
- **UUID**: `UUID` type. Indexed, compact (16 bytes vs 36 chars).

`NULL` means "unknown or not applicable." If a column should always have a value, declare `NOT NULL` and provide a default. Half-populated nullable columns are a major source of bugs.

## Common patterns

### Soft deletes
Add `deleted_at TIMESTAMPTZ NULL`. Filter `WHERE deleted_at IS NULL` in every read query. Pros: recoverability, audit trail. Cons: every query must filter, unique constraints get awkward (`UNIQUE (email) WHERE deleted_at IS NULL` partial index), foreign keys to deleted rows become weird.

Use soft deletes when: data needs to be recoverable, regulatory holds may apply, downstream systems may still reference the row.
Don't use them when: you have a hard "right to be forgotten" requirement (GDPR), or for very high-volume tables where the dead rows accumulate forever.

### Audit / history tables
A separate `<table>_history` table populated by trigger or application logic, capturing `(id, snapshot_of_columns, changed_at, changed_by, change_kind)`. Append-only. Don't try to make the main table do double duty as a history table — `valid_from` / `valid_to` columns work, but they make every query painful.

### Multi-tenancy
Three approaches, in order of complexity:

1. **Tenant column on every table** — `tenant_id` on every row, every query filters by it, ideally enforced via Postgres RLS (Row-Level Security). Simplest to operate, what most SaaS uses.
2. **Schema-per-tenant** — separate Postgres schema per tenant. Easier per-tenant backups, harder cross-tenant queries, breaks down past a few thousand tenants (catalog bloat).
3. **Database-per-tenant** — full isolation, much higher operational cost. Only justified for large enterprise customers with hard isolation requirements.

Pick (1) by default. Combine with RLS so a missing `WHERE tenant_id = ?` cannot leak data.

### Polymorphic associations
"A `comment` can belong to a `post` or a `video`." Three options:

1. **Two nullable FKs** — `post_id NULLABLE`, `video_id NULLABLE`, with a CHECK constraint that exactly one is set. FK integrity preserved. Adds a column per new owner type.
2. **Type + ID columns** — `commentable_type TEXT, commentable_id UUID`. Cannot use FKs (the target table varies). Familiar from Rails, but you lose referential integrity.
3. **Separate join tables** — `post_comments`, `video_comments`. Most relational. Most boilerplate.

Default to (1) for small numbers of types; reach for (3) when types diverge significantly. (2) is usually the wrong answer despite its popularity.

### Many-to-many
Junction table with composite PK `(a_id, b_id)`, plus indexes on both columns individually if you query in both directions. Add metadata (`created_at`, `role`, `weight`) on the junction row when needed. Don't be afraid to give the junction table a name from the domain (`memberships`, `enrollments`) rather than `users_groups`.

### Hierarchies / trees
- **Adjacency list** — `parent_id` column. Simple inserts, recursive CTEs for traversal. Good default in Postgres.
- **Materialized path** — `path TEXT` like `'root.parent.child'`. Easy ancestor queries, harder moves.
- **Closure table** — separate table with one row per ancestor-descendant pair. Great for queries, expensive to maintain.
- **Nested sets** — left/right values. Beautiful in theory, miserable to update.

For most needs in Postgres: adjacency list + recursive CTE, or the `ltree` extension.

## Indexing strategy

The mental model: an index is a sorted lookup structure. The query planner uses it when (a) the access pattern matches the index's leading columns and (b) the planner's stats suggest using the index will be cheaper than scanning.

### When to add an index

- Columns used in `WHERE`, `JOIN`, `ORDER BY`, `GROUP BY`.
- Foreign key columns (always).
- Columns with high selectivity (many distinct values relative to row count). An index on a boolean is rarely useful.
- Columns used for uniqueness (UNIQUE indexes are also lookup indexes — two for one).

### When not to add an index

- Tiny tables (a few thousand rows) — sequential scan is fine.
- Write-heavy tables where read patterns are unclear — every index slows writes.
- Columns with very low cardinality (status flag with 2 values) — partial indexes are usually better.
- "Just in case" — every index has a maintenance cost. Add when the query is slow and `EXPLAIN` shows a sequential scan that hurts.

### Composite indexes

`CREATE INDEX ON orders (customer_id, created_at DESC);`

Order matters. This index serves:
- `WHERE customer_id = ?`
- `WHERE customer_id = ? AND created_at > ?`
- `WHERE customer_id = ? ORDER BY created_at DESC`

It does **not** efficiently serve `WHERE created_at > ?` alone — the leading column is `customer_id`. The leftmost-prefix rule is the single most useful thing to know about composite indexes.

### Partial indexes

Index only the rows you care about:

```sql
CREATE INDEX ON orders (created_at) WHERE status = 'pending';
```

Smaller, faster, and the planner uses it whenever the WHERE clause matches. Excellent for "active" subsets in soft-deleted tables, or hot states in workflow tables.

### Covering indexes

`CREATE INDEX ON users (email) INCLUDE (display_name);` — the index can answer the query without touching the table heap. Helps when you have a hot read of a few columns.

### Don't index your way out of a bad query

If a query is slow, first ask: is the query the right shape? Adding indexes to bandaid an N+1 or a missing JOIN condition makes the schema worse.

## Transactions and isolation

The default isolation level on most databases is `READ COMMITTED`. This prevents dirty reads but allows non-repeatable reads and phantoms. Most application code is written assuming this, often unknowingly.

Levels, from weakest to strongest:

| Level | Prevents dirty reads | Prevents non-repeatable reads | Prevents phantoms |
|---|---|---|---|
| READ UNCOMMITTED | ❌ | ❌ | ❌ |
| READ COMMITTED | ✅ | ❌ | ❌ |
| REPEATABLE READ | ✅ | ✅ | ❌ (in MySQL/Postgres uses snapshots, mostly OK) |
| SERIALIZABLE | ✅ | ✅ | ✅ |

In Postgres specifically, `REPEATABLE READ` gives you a snapshot for the duration of the transaction — strong enough for most multi-row consistency needs. `SERIALIZABLE` gives you the strongest guarantee but can fail with serialization errors that the application must retry.

### When to escalate isolation

- Reading multiple rows that must be consistent with each other (e.g., balance across accounts) → `REPEATABLE READ`.
- Reading and then writing based on what you read, where another concurrent transaction could invalidate your read → `SERIALIZABLE` or use explicit locking (`SELECT ... FOR UPDATE`).
- Counters and balances → `SELECT ... FOR UPDATE` on the row, or use atomic SQL (`UPDATE accounts SET balance = balance + $1`) which is naturally atomic per-row.

### Keep transactions short

Long transactions hold locks, hold MVCC tuple visibility (Postgres bloat), and increase deadlock probability. A transaction should be a tight critical section, not a place to do HTTP calls or long computation. **Open, write, commit.**

## Migrations

The non-negotiable rules:

1. **Migrations are forward-only in production.** "Down migrations" are a development convenience; in production you write a new forward migration to fix things.
2. **Every migration is reviewed.** Schema changes are higher-stakes than code changes — they're permanent.
3. **Migrations and code deploy in compatible order.** The pattern that works:
   - **Add a new column / table** (nullable, defaulted, no FK yet) → deploy.
   - **Deploy code that writes to both old and new** → deploy.
   - **Backfill existing rows** → deploy if needed.
   - **Switch reads to the new column** → deploy.
   - **Stop writing the old column** → deploy.
   - **Drop the old column** → migration.

Each step is independently reversible. A "rename column" migration looks simple but is actually six steps if the table is in use.

### Things that lock the table (in Postgres)
- Adding a column with a non-volatile default (Postgres ≥ 11): cheap, OK.
- Adding a column with a volatile default or with `NOT NULL` and no default on a populated table: rewrites the whole table — *don't*. Add nullable, backfill in batches, then `SET NOT NULL` after.
- Adding an index without `CONCURRENTLY`: blocks writes for the duration. Use `CREATE INDEX CONCURRENTLY` always in production.
- Renaming a column: fast in catalog, but breaks any in-flight queries and ORM-generated SQL — coordinate with code.
- Adding a CHECK constraint: scans the table to validate. Use `NOT VALID` then `VALIDATE CONSTRAINT` later.
- Foreign keys: similar — `NOT VALID` then `VALIDATE`.

When in doubt, search for the operation in your DB engine's docs under "transparency" or "lock-free." Postgres has gotten dramatically better here over the last decade, but old habits in framework migrations sometimes haven't caught up.

## ORM use, sanely

Use an ORM. But:

- **Read the SQL it generates.** Turn on query logging in development. The expensive query is always in there somewhere.
- **Pre-load explicitly.** ORMs default to lazy loading — that's where N+1 lives. Eagerly load (`select_related` / `prefetch_related` / `joinedload` / `with relations`) the things you'll touch.
- **Drop to raw SQL for complex reads.** Reporting queries, aggregations, window functions — write them as SQL. ORMs are great for CRUD; they're bad at analytical queries.
- **Don't let the ORM design the schema.** Generate the schema from the migration tool (Alembic, Prisma, Drizzle, Knex), not from "let me sync my models." The schema must be reviewed and intentional.

## Smells that suggest the schema is wrong

- A table called `data`, `info`, `metadata`, `extra`. What is it actually about?
- A column called `type` that switches the meaning of other columns. (Use separate tables, or polymorphic with discipline.)
- More than ~30 columns on one table. Probably two or three things conflated.
- Column names like `field1`, `field2`, `param1`. The schema isn't designed; the schema is "we'll figure it out at runtime."
- Many nullable columns where most are unset for any given row. Sparse table — should probably be split or use JSONB.
- Encoded data in columns: comma-separated lists, JSON in TEXT, pipe-delimited tags. The DB can't index, validate, or join on encoded blobs.
- Booleans masquerading as enums (`status TEXT` with values `'yes'`, `'no'`, `'maybe'`). Pick one or the other, not both.
- Timestamps stored as strings, integers, or local time. All three break.

## A reasonable design workflow

1. List the **entities** and their **identifiers**.
2. List the **relationships** between them with **cardinality** and **ownership**.
3. List the **queries** the application will run, in priority order.
4. List the **invariants** that must hold (`balance >= 0`, exactly one address marked default, etc.).
5. Sketch the schema. Apply normalization rules.
6. Add **constraints** for the invariants (NOT NULL, CHECK, UNIQUE, FK).
7. Add **indexes** matching the queries from step 3.
8. Walk through each query mentally and confirm it's served well by the schema and indexes.
9. Identify **migration risks** for the high-traffic tables; design changes to be online-safe.
10. Document the model — at minimum, comments on tables and non-obvious columns. ER diagrams age fast; schema-with-comments doesn't.