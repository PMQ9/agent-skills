---
name: django
description: Use this skill for any work involving Django or Django REST Framework — including building views, models, migrations, querysets, serializers, admin, middleware, settings, URL routing, authentication, permissions, signals, forms, templates, Channels (websockets), Celery tasks, async views, caching, testing with pytest-django, performance work (N+1, query analysis), security (CSRF, auth, session), or deployment (gunicorn/uvicorn, ASGI/WSGI, static files). Trigger on settings.py, models.py, urls.py, manage.py, .py files in a Django project, mentions of "Django", "DRF", "ORM", "migration", "queryset", "serializer", "admin site", "ModelViewSet", "APIView", or "my Django app". Also trigger when a user is choosing between web frameworks and Django is one of them.
---

# Django

Django is a batteries-included framework optimized for *not making you make a thousand small decisions*. The ORM, admin, auth, forms, templates, sessions, migrations, and i18n are all there, designed to work together, with sensible defaults. Working with the framework — its idioms, its conventions, its lifecycle — produces clean code fast. Working against it produces a tangle.

The high-leverage advice: lean into Django's conventions for as long as possible, and only deviate when you have a concrete reason. The hardest-to-maintain Django codebases are the ones where someone fought the framework rather than learned it.

## Project layout

The convention that scales:

```
myproject/
├── manage.py
├── pyproject.toml          # or requirements/ if not using pyproject
├── config/                 # the "project" — settings, root urls, asgi/wsgi
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   ├── prod.py
│   │   └── test.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/                   # your apps live here
│   ├── users/
│   ├── billing/
│   └── catalog/
└── templates/              # project-wide templates (overrides)
```

Reasoning:

- **Split settings.** A single `settings.py` becomes a hairball. `base.py` holds shared config; per-environment files import from base and override. `prod.py` raises `ImproperlyConfigured` if `SECRET_KEY` is missing. `test.py` swaps in a faster password hasher and an in-memory cache.
- **An "app" is a unit of cohesion**, not a microservice. Group by domain (`billing`, `catalog`) rather than by layer (`models`, `views`). When an app gets too big — say, >2000 lines of models — split by sub-domain.
- **`config/` (or `core/`) for the project package**, not the project name. It saves you from `myproject.myproject.settings` Russian-doll imports.

## Settings

Things every production settings file needs:

```python
# config/settings/prod.py
from .base import *  # noqa

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
SECRET_KEY = env("SECRET_KEY")  # raises if missing

# Security
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"), conn_max_age=600)}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                       "LOCATION": env("REDIS_URL")}}

LOGGING = {  # JSON to stdout, no FileHandler in containers
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"json": {"()": "pythonjsonlogger.jsonlogger.JsonFormatter"}},
    "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["stdout"], "level": env("LOG_LEVEL", default="INFO")},
}
```

Use `django-environ`, `pydantic-settings`, or hand-rolled `os.environ` parsing. Whichever you pick, **never put secrets in settings files committed to Git** — they come from the environment. (See the secrets-management skill.)

`SECURE_PROXY_SSL_HEADER` is required when behind a load balancer that terminates TLS, otherwise Django thinks every request is HTTP and `SECURE_SSL_REDIRECT` causes an infinite loop.

## Models and the ORM

The ORM is one of Django's strongest pieces, and the place beginners most often shoot themselves in the foot.

### Designing models

- **Default explicit primary keys.** Set `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"` (Django 3.2+ already does this for new projects). Consider UUIDs for externally-exposed IDs to avoid leaking row counts.
- **`null=True` on `CharField`/`TextField` is almost never right.** Use `blank=True` (form-level "may be empty") with `default=""`. Two ways to represent "empty" — empty string and NULL — invites bugs.
- **`on_delete` is required** since 1.9. Pick deliberately: `CASCADE` (delete dependents), `PROTECT` (refuse deletion if dependents exist — often the right safety choice), `SET_NULL` (with `null=True`), `SET_DEFAULT`, `DO_NOTHING` (you handle it).
- **Indexes on what you query.** Foreign keys get an index automatically. Add `db_index=True` or `Meta.indexes` for fields you filter or order by often. Composite indexes for `(field_a, field_b)`-style queries.
- **`Meta.ordering` has a cost.** It's applied to *every* query unless overridden. If you don't actually need ordering by default, omit it.
- **`unique_together` is deprecated** in favor of `UniqueConstraint` in `Meta.constraints`. The latter supports conditional constraints and is more expressive.
- **CheckConstraints in the database**, not just in Python. `CheckConstraint(check=Q(amount__gte=0), name="amount_non_negative")` — the DB is your last line of defense.

### Querysets, the major performance hazard

Querysets are **lazy** and **chainable**. They don't hit the database until iterated, sliced (with steps), bool'd, or pickled. This is great until you forget and trigger N+1.

The two methods you must reach for constantly:

- **`select_related`** — for ForeignKey and OneToOne. Does a SQL JOIN; one query.
- **`prefetch_related`** — for reverse FK and ManyToMany. Issues a second query and stitches results in Python.

```python
# WRONG — N+1: one query for orders, then one per order for the user
orders = Order.objects.all()
for o in orders:
    print(o.user.email)         # query per iteration

# RIGHT
orders = Order.objects.select_related("user")

# WRONG — N+1 on the items
for o in Order.objects.all():
    for item in o.items.all():  # query per order
        ...

# RIGHT
for o in Order.objects.prefetch_related("items"):
    for item in o.items.all():  # uses prefetched cache
        ...
```

When prefetching with filters, use `Prefetch("items", queryset=Item.objects.filter(active=True))`.

### Other queryset rules

- **`only` and `defer`** load partial fields. Useful for big rows; trap if you then access a deferred field (silent extra query).
- **`values` and `values_list`** return dicts/tuples instead of model instances. Faster, no model overhead. Flat list: `values_list("id", flat=True)`.
- **`bulk_create` and `bulk_update`** are 10–100× faster than per-instance saves. Caveat: signals don't fire (often desirable; sometimes a surprise).
- **`update()` on a queryset** issues a single SQL `UPDATE`. Skips `save()`, `save()` signals, and `auto_now`. That's a feature for bulk updates and a hazard for things you forgot.
- **`F` expressions** for atomic database-side updates: `Account.objects.filter(id=x).update(balance=F("balance") - 1)` — no read-modify-write race.
- **`exists()`** instead of `if qs:` — generates a more efficient query.
- **`count()`** is a `SELECT COUNT(*)` — a real query. Don't put it in a loop.

### N+1 detection

- **`django-debug-toolbar`** in dev. Watch the SQL panel.
- **`django-extensions`** has a `--print-sql` option for `shell_plus`.
- **`nplusone`** package fails tests when N+1 is detected. Genuinely worth installing.
- In production: log slow queries via DB-level slow query log; alert on query count per request via middleware (`connection.queries` length under DEBUG, or APM-level instrumentation).

## Migrations

Django's migrations are *the* feature that makes schema evolution livable.

- **Always check `makemigrations` output before committing.** Sometimes Django's autodetector picks up changes you didn't mean to make (a model `Meta.ordering` change creates a migration; a default change does too).
- **Migrations live in version control.** Forever. Don't edit a migration that's been applied to any environment other than your local dev. Make a new one.
- **Migrations are forward-only in practice.** Reversibility is nice but rarely real — once data has been transformed, "reverse" is a fantasy. Plan deploys that way.
- **Long-running migrations on big tables will lock you out** in Postgres. `ALTER TABLE ADD COLUMN ... DEFAULT ...` rewrites the table. The safe pattern is multi-step:
  1. Add column nullable, no default.
  2. Backfill in batches, separately.
  3. Add the default and `NOT NULL` constraint.
  4. Code starts using it.
- **Data migrations** (`RunPython`) for one-time data transforms. They're slow, single-transaction by default, and run on every fresh DB setup forever. Use them sparingly; consider one-off scripts instead for big backfills.
- **`squashmigrations`** when migration history gets unwieldy. Keep it tidy.

For zero-downtime deploys, the rule is: **the new code must work against the old schema, and the old code must work against the new schema.** Never break that invariant in a single deploy.

## Views

### Function-based vs. class-based

Both work. Use the simpler one for the job:

- **Function-based** views are great for one-off pages and APIs. Easy to read top-to-bottom.
- **Class-based** views shine when you have shared structure across multiple endpoints (CRUD on a resource, or DRF). The Django generic CBVs (`ListView`, `DetailView`, etc.) save real boilerplate but have a steep learning curve — there's a lot of method-resolution-order to internalize.
- **DRF's class-based views** are excellent and idiomatic for APIs.

When using CBVs, lean on the framework's hooks (`get_queryset`, `get_context_data`, `form_valid`) rather than overriding `dispatch` or `get` wholesale. The hooks compose; the lower-level methods don't.

### Forms

For server-rendered HTML, Django forms (especially `ModelForm`) are excellent. Validation hooks (`clean_<field>`, `clean`), error rendering, CSRF, all integrated. Don't reinvent on top of plain `request.POST`.

For APIs, you don't use forms — you use DRF serializers (or pydantic via `django-ninja`).

## Django REST Framework

DRF is the default for JSON APIs in Django. Modern alternative is `django-ninja` (FastAPI-like, pydantic-based, leaner) — worth a look for greenfield, especially if your team likes pydantic. DRF still wins on ecosystem maturity.

### Patterns

- **`ModelViewSet`** for full CRUD on a resource is concise and idiomatic. Drop down to `GenericViewSet` + mixins if you only need some actions, or `APIView` for fully custom.
- **Serializers do double duty: validation and representation.** Mostly that's fine. When their use diverges (request shape ≠ response shape), use separate serializers.
- **`get_serializer_class`** to vary serializer by action (`list` vs `retrieve` vs `create`).
- **Nested writes are fraught.** DRF's automatic nested serializer writes are limited; for non-trivial nested writes, override `create`/`update` explicitly. Don't fight the framework here — write the SQL-level logic you need.
- **Permissions and authentication are pluggable.** `IsAuthenticated`, `DjangoModelPermissions`, custom `BasePermission` subclasses. Compose with `&`/`|`. Be deliberate; the wrong default is a security bug.
- **Throttling** via `DEFAULT_THROTTLE_CLASSES` (`AnonRateThrottle`, `UserRateThrottle`). Set them; the framework gives you basic abuse protection for free.
- **Pagination:** cursor-based for anything that grows. The default `PageNumberPagination` becomes inconsistent under inserts.
- **Schemas via `drf-spectacular`.** Generates OpenAPI. Avoid the older `coreapi`-based stuff; it's been superseded.

### Performance in DRF

The classic DRF perf trap is N+1 in serializers. A `ManyRelatedField` or nested serializer that walks relations triggers a query per row. Audit `get_queryset` to apply `select_related`/`prefetch_related` for everything the serializer touches.

## Authentication and permissions

- **Use `AbstractUser` or `AbstractBaseUser`** to extend the user model. **Set `AUTH_USER_MODEL` before the first migration.** Changing it later is genuinely painful.
- **Email as username** is usually what you want. `AbstractBaseUser` with `email = EmailField(unique=True)` and a custom manager.
- **Password storage:** Django's `Argon2PasswordHasher` is the recommended top hasher. Add it to `PASSWORD_HASHERS`.
- **Session vs. token vs. JWT:**
  - **Session auth** (cookie-based): default for browser-based apps. Secure, simple, supports CSRF. Use it.
  - **Token auth** (DRF's): a long-lived random token per user. Fine for first-party clients. Rotation is your problem.
  - **JWT** (`djangorestframework-simplejwt`): popular for SPAs, but brings real complexity (refresh tokens, revocation, rotation). Don't reach for JWT just because it sounds modern; cookies + session auth is genuinely fine for most apps. Use JWT when you have a real reason (cross-domain SSO, mobile clients with offline support, third-party integrations).
- **CSRF:** Django's CSRF middleware protects session-authenticated requests automatically. **`@csrf_exempt` is a code smell.** If you're disabling CSRF, you'd better know why.
- **Object-level permissions:** the built-in permission system is per-model. For per-object ("this user owns this row"), use `django-guardian` or implement check methods in views/permissions.

## Caching

Django has `cache`. Use it.

- **Backend: Redis.** Default to `django.core.cache.backends.redis.RedisCache` (Django 4.0+; earlier projects used `django-redis`).
- **Key prefixes** to avoid collisions in shared Redis (`KEY_PREFIX = "myapp"` in settings).
- **Versioning** built in (`cache.set(key, val, version=2)`) for migrations.
- **Per-view caching** (`@cache_page`) is a hammer; works great for genuinely public pages, breaks personalization.
- **Per-fragment caching** in templates (`{% cache 600 sidebar %}`) is finer-grained.
- **Low-level caching** (`cache.get`, `cache.set`) is the most flexible; combine with a **stale-while-revalidate** wrapper for resilience (see the resilience-patterns skill).
- **Cache invalidation** is hard. Pick one: TTL-based (simple, sometimes stale) or event-based (signal handlers / explicit invalidation; more complex, fresher). TTL-only is the default; event-based when correctness matters.

## Async views and Channels

Django supports async views (`async def view(request): ...`) and async ORM (`Model.objects.aget`, `.acreate`, etc.) since 4.x.

- **Async views are useful for I/O fan-out** (call three external services in parallel with `asyncio.gather`). Don't wholesale-rewrite to async without a reason — Django's request handling is sync-friendly and most ORM use is fine sync.
- **The ORM is "async-compatible"**, not natively async. Many sync paths still happen under the hood. Use `sync_to_async` for sync-only operations.
- **Channels** for websockets. Adds a layer (Daphne or uvicorn under ASGI, plus a channel layer like Redis). Real complexity; ensure you need full-duplex before adopting. For server-to-client push, **server-sent events (SSE)** are simpler and often enough.

## Background work — Celery (and alternatives)

For non-trivial background work, **Celery + Redis or RabbitMQ** is the established choice. Smaller-footprint alternatives: **`django-q2`**, **`huey`**, **`dramatiq`**, **`django-rq`**. For one-off scheduled jobs, a Postgres-backed queue like **`procrastinate`** is increasingly popular (no separate broker).

Whichever you pick:

- **Idempotent tasks.** Tasks can run twice (network blips, redeploys). Design accordingly.
- **Task arguments are JSON.** Pass IDs, not model instances. Re-fetch in the task body.
- **Set timeouts, retries with backoff.** A task without `time_limit` is a worker that hangs forever.
- **Don't use `@shared_task` for long-lived work.** Long tasks should checkpoint progress and be resumable.
- **Monitor queue depth.** A growing queue is the leading indicator of trouble.

## Testing

- **`pytest-django`** beats Django's built-in `unittest`-based test runner for ergonomics. Fixtures, parametrization, better output.
- **`@pytest.mark.django_db`** for DB access. By default, each test runs in a transaction that's rolled back.
- **Factories with `factory_boy`** > fixtures. Loadable, composable, no stale YAML.
- **`Client` and `APIClient`** for view-level tests. They're integration-flavored and catch real bugs.
- **Don't mock the ORM.** Use a real DB (sqlite for unit tests if speed-critical, but Postgres for anything DB-specific). Mocked ORMs are tests of mocks, not code.
- **Settings overrides:** `@override_settings` per test, `settings` fixture in pytest-django.
- **`SimpleTestCase`** when you genuinely don't need the DB — faster.

## Performance

In rough order of leverage:

1. **Eliminate N+1 with `select_related` / `prefetch_related`.** Almost always the highest-leverage fix.
2. **Add indexes** for filtered/ordered fields. Use `EXPLAIN ANALYZE` to confirm.
3. **Cache expensive computations**, especially anything called per-request.
4. **Use `bulk_create` / `bulk_update`** for write-heavy paths.
5. **Pull only the columns you need** — `only`, `defer`, `values`.
6. **Move slow work to background tasks.** A 200ms request shouldn't include a 5s third-party API call; queue it.
7. **Connection pooling at the DB.** PgBouncer in transaction-pooling mode is the standard pattern. Be aware of its quirks (no session-level state, no `LISTEN/NOTIFY`).

## Security

Django gets a lot right by default. Don't undo it.

- **CSRF** on by default for session auth. Don't disable it without a reason.
- **`SECURE_*` settings** all the way on (HSTS, SSL redirect, secure cookies). See the settings example above.
- **Keep `DEBUG = False` in any non-dev environment.** `DEBUG=True` exposes settings, env, and traceback to the client.
- **`ALLOWED_HOSTS`** properly set. Wildcards are a footgun.
- **SQL injection** is hard with the ORM, easy if you use `raw()` or `extra()` with string-formatted parameters. Always parameterize.
- **XSS:** templates auto-escape by default. `{% autoescape off %}` and `mark_safe` are how you turn it off; they should be rare and audited.
- **File uploads:** validate MIME and content, not just extension. Store outside the public path and serve through a view, or use signed URLs.
- **Password reset and email enumeration:** the default `PasswordResetView` doesn't reveal whether an email exists; preserve that behavior in custom flows.
- **`django-axes`** for login throttling against brute-force.
- **Subscribe to django-announce** for security advisories. Patch promptly.

## Deployment

The standard, boring, correct stack:

- **Gunicorn** (sync) or **uvicorn** (ASGI/async). Number of workers ≈ `2 * CPU + 1` is the rule of thumb; tune from there. Threads per worker for I/O-bound work.
- **A reverse proxy in front** (nginx, Caddy, an ALB) for TLS termination and static file serving. Or use **WhiteNoise** to serve static files from Gunicorn — fine for small/medium services.
- **Static files:** `collectstatic` at build time. Serve from CDN or via WhiteNoise.
- **Media files** (user uploads): **never on the web server's local disk** in a multi-instance deploy. S3 / GCS / Azure Blob via `django-storages`.
- **Migrations on deploy:** run *before* the new code starts. Backwards-compatible migrations only (additive first, breaking only after old code is gone).
- **Health check endpoint:** a tiny view returning 200 if the DB is reachable. Don't put expensive logic here.
- **Hosted options** (`Render`, `Fly`, `Railway`) are great for small Django apps; reach for k8s when you outgrow them, not before.

## Anti-patterns to push back on

- **Logic in templates.** Templates render. Computation goes in views or services.
- **Fat models *and* fat views.** Pick a side. Often the right answer is a `services/` module — plain Python functions that orchestrate models — keeping models focused on data and views focused on HTTP.
- **Signals as load-bearing infrastructure.** Signals are fine for cross-cutting concerns (audit log, cache invalidation). They're a footgun for core business logic — order of execution is implicit, debugging is hard, side effects accumulate. Prefer explicit calls.
- **One giant `models.py`** with 30+ models. Split.
- **Every endpoint behind `@login_required` except the ones with `@csrf_exempt`** — usually a sign authentication boundaries weren't designed.
- **Custom authentication** invented from scratch. Use `django-allauth` or `django-rest-framework-simplejwt`. Cryptography is not a place to be creative.
- **Disabling migrations** ("we'll just use `--fake`"). Migrations are your friend; they're not the enemy of velocity.
- **`save()` overrides for "always do X on save".** Often a signal would be wrong but a method that callers must invoke is right. Even better: a service function that wraps save + side effect.
- **Putting business logic in DRF serializers.** Serializers serialize. Validation, sure. Orchestration of saves across multiple models, or external calls — no. Pull it into a service function, call it from `create`/`update`.

## Quick checklist before shipping a Django service

- `DEBUG = False`, `ALLOWED_HOSTS` set, `SECRET_KEY` from environment.
- All `SECURE_*` settings on.
- Custom user model in place from day one.
- Database has indexes on filtered/joined columns.
- Querysets use `select_related`/`prefetch_related` where serialized.
- Tests run with `pytest-django`, real Postgres, factories.
- Migrations are reviewed; no destructive ops in a single deploy.
- Static files served via CDN or WhiteNoise; media on object storage.
- Background tasks are idempotent, with timeouts and retries.
- Logs go to stdout, structured (JSON).
- Health endpoint exists and is wired to the load balancer.
- Monitoring covers RPS, latency histogram, error rate, DB connection pool, queue depth.
- Secrets come from a secret manager, not settings files.
