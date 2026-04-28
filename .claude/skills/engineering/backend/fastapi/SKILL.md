---
name: fastapi
description: Building production FastAPI services — project structure, dependency injection, Pydantic validation, async SQLAlchemy/SQLModel, authentication, background work, testing, and observability. Use whenever the user is writing a Python web API with FastAPI, structuring a new FastAPI project, adding endpoints, integrating a database, debugging async/await issues, or asking about Python backend best practices. Triggers on "FastAPI," "Pydantic," "Starlette," "uvicorn," "async def" + web context, and any Python-backend design question.
---

# FastAPI

Production-shaped guidance. Targets FastAPI 0.115+ and Pydantic v2.

## When FastAPI is the right choice

FastAPI is the default for new Python web services in 2026. It's the right pick when:
- The team is already strong in Python (ML, data, scripting heritage).
- You want async I/O (DB, HTTP calls, queues) with low ceremony.
- You want OpenAPI/JSON schema for free.
- You're building APIs, not server-rendered HTML (for that, Django still wins).

It is *not* magic — async Python is faster than sync Python on I/O-bound work but slower than Go/Node on raw CPU. Reach for FastAPI for the developer ergonomics; reach for Go/Rust if you're CPU-bound at the edge.

## Project structure

Don't follow tutorials that put everything in `main.py`. Use a layout that scales:

```
app/
├── main.py                 # FastAPI app instance, lifespan, middleware, router includes
├── config.py               # Settings via pydantic-settings
├── api/
│   ├── deps.py             # Shared dependencies (db, current user, pagination)
│   ├── errors.py           # Exception handlers
│   └── v1/
│       ├── __init__.py     # api_router = APIRouter(); includes the routers below
│       ├── users.py
│       ├── orders.py
│       └── ...
├── core/
│   ├── security.py         # Password hashing, JWT, OAuth helpers
│   └── logging.py
├── db/
│   ├── base.py             # SQLAlchemy Base, engine, session factory
│   ├── session.py          # get_session() dependency
│   └── migrations/         # Alembic
├── models/                 # SQLAlchemy ORM models (DB layer)
│   ├── user.py
│   └── order.py
├── schemas/                # Pydantic models (API layer) — separate from ORM models
│   ├── user.py
│   └── order.py
├── services/               # Business logic / use cases
│   ├── users.py
│   └── orders.py
├── repositories/           # Data access (optional layer; see below)
└── workers/                # Background jobs, scheduled tasks
tests/
pyproject.toml
```

The split that matters most: **schemas (API contracts) ≠ models (DB rows) ≠ services (logic).** Don't return ORM objects directly from endpoints; map them to response schemas. Don't put business logic in routes. Routes are thin: parse → call service → return schema.

The `repositories/` layer is optional. For small apps, services can use the SQLAlchemy session directly. For larger apps with complex queries, having a `UserRepository` that owns SQL keeps services from drowning in query code.

## Configuration

Use `pydantic-settings` — typed, validated, environment-driven. Never hardcode, never `os.environ.get` ad-hoc.

```python
# app/config.py
from functools import lru_cache
from pydantic import PostgresDsn, RedisDsn, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    debug: bool = False

    database_url: PostgresDsn
    redis_url: RedisDsn | None = None

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 3600

    cors_origins: list[str] = []

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Inject via `Depends(get_settings)` so tests can override.

## App entry point and lifespan

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.errors import register_error_handlers
from app.config import get_settings
from app.db.base import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # e.g., warm up connections, register metrics
    yield
    # Shutdown
    await engine.dispose()

settings = get_settings()

app = FastAPI(
    title="My Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # disable in prod or auth-gate
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(api_router, prefix="/api/v1")
```

Use `lifespan` (not deprecated `on_event`) for startup/shutdown.

## Pydantic models — discipline

Pydantic v2 is fast and strict by default. Take advantage:

```python
# app/schemas/user.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=80)

class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=128)

class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)

class UserPublic(UserBase):
    model_config = ConfigDict(from_attributes=True)  # allows ORM → schema conversion

    id: UUID
    created_at: datetime
```

Patterns to follow:

- **Separate input and output schemas.** Don't reuse one model for both — they have different fields (no `password` in output, no `id` in input).
- **Never return ORM objects from endpoints.** Use `from_attributes=True` and explicit response schemas. Prevents accidental leakage of internal fields (`hashed_password`, `internal_notes`) and gives you a stable wire contract.
- **Use specific types.** `EmailStr`, `HttpUrl`, `UUID`, `datetime`, constrained ints/strs. Validation is free.
- **Validate at the boundary, trust internally.** Parse once on input; downstream code can assume valid types.

## Dependencies — DI without a framework

FastAPI's `Depends` is the DI system. Use it for:

```python
# app/api/deps.py
from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.core.security import decode_token
from app.models.user import User
from app.services.users import UserService

DbSession = Annotated[AsyncSession, Depends(get_session)]

async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = await UserService(db).get(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive user")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]
```

Use `Annotated` aliases — they make endpoint signatures readable and the DI obvious.

```python
# app/api/v1/users.py
from fastapi import APIRouter
from app.api.deps import DbSession, CurrentUser
from app.schemas.user import UserPublic, UserUpdate
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserPublic)
async def me(current: CurrentUser):
    return current

@router.patch("/me", response_model=UserPublic)
async def update_me(payload: UserUpdate, current: CurrentUser, db: DbSession):
    return await UserService(db).update(current.id, payload)
```

## Database — async SQLAlchemy 2.0

Use SQLAlchemy 2.0 async style. SQLModel is fine for prototypes but the ecosystem and docs are stronger on plain SQLAlchemy + Pydantic.

```python
# app/db/base.py
from sqlalchemy.ext.asyncio import (
    AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    str(settings.database_url),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,         # detect stale connections
    pool_recycle=1800,          # recycle every 30m
    echo=settings.debug,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass
```

```python
# app/db/session.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import SessionLocal

async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

This commits on success and rolls back on error per request. For finer transaction control, drop the auto-commit and let services manage transactions explicitly.

```python
# app/models/user.py
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

Avoid lazy loading in async code — it explodes with `MissingGreenlet` errors. Eagerly load relationships:

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

stmt = select(Order).options(selectinload(Order.items)).where(Order.user_id == uid)
result = await db.execute(stmt)
orders = result.scalars().all()
```

For migrations: Alembic, configured for async. Use one-migration-per-PR review discipline. See the `database-design` skill for migration safety patterns.

## Service / repository layer

Services own the verbs of the domain; repositories own the SQL. For most apps it's fine to combine them:

```python
# app/services/users.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            display_name=data.display_name,
        )
        self.db.add(user)
        await self.db.flush()       # populate user.id without committing
        return user

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        user = await self.db.get(User, user_id)
        if not user:
            raise LookupError("User not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.db.flush()
        return user
```

`exclude_unset=True` is the PATCH-friendly way to apply partial updates — only fields the client sent.

## Authentication

For most APIs: **OAuth2 Password (Bearer)** with JWTs, or session cookies for browser apps. Use a tested library; don't roll JWT verification yourself.

```python
# app/core/security.py
from datetime import datetime, timezone, timedelta
import jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")  # argon2 > bcrypt for new apps

def hash_password(plain: str) -> str:
    return _pwd.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)

def create_access_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "iat": now, "exp": now + timedelta(seconds=s.jwt_ttl_seconds)},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )

def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
```

Notes:

- **Argon2id** is the modern password hash. Bcrypt is fine; argon2 is better for new builds.
- **JWTs are not session tokens.** They cannot be revoked without an additional store. For browser apps with logout, prefer server-side sessions (Redis-backed, opaque token, lookup on each request) over JWTs. JWTs shine for inter-service auth.
- **Refresh tokens** for long-lived auth: short-lived access JWT + long-lived refresh token (opaque, server-stored, revocable).
- For external auth, use Authlib or a managed provider (Auth0, Clerk, Supabase Auth, WorkOS). Don't implement OAuth flows by hand.

## Error handling

Define a small set of domain errors and map them to HTTP at the boundary:

```python
# app/api/errors.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

class AppError(Exception):
    status_code = 500
    code = "internal_error"
    def __init__(self, message: str = "Something went wrong"):
        self.message = message

class NotFound(AppError):
    status_code = 404; code = "not_found"

class Conflict(AppError):
    status_code = 409; code = "conflict"

class Forbidden(AppError):
    status_code = 403; code = "forbidden"

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_err(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
```

Services raise `NotFound`, `Conflict`, etc. Routes don't translate these — the handler does. This keeps service code clean and HTTP-agnostic (testable without a request).

## Async correctness — avoid the common mistakes

- **Don't call sync I/O from `async def` handlers.** It blocks the event loop. Wrap with `asyncio.to_thread` for one-off sync calls; better, use the async client of the underlying library (`asyncpg`, `httpx.AsyncClient`, `aioredis`, `aiokafka`).
- **`time.sleep()` blocks the event loop.** Use `await asyncio.sleep()`.
- **`requests` blocks.** Use `httpx.AsyncClient`.
- **Sync `psycopg2` blocks.** Use `asyncpg` (or `psycopg` v3 in async mode).
- **CPU-heavy work blocks.** Offload to a worker queue (Arq, Celery, Dramatiq) or spawn a process pool.
- **Database session is per-request.** Don't share `AsyncSession` across requests or tasks.

A handler that does `def` instead of `async def` is fine — FastAPI runs it in a threadpool. That's actually the right choice if you must call a sync library and don't want to wrap each call. Pick one or the other; don't mix in the same function.

## Background tasks

Three tiers, increasing in robustness:

1. **`BackgroundTasks`** built into FastAPI — runs after the response. Fine for "send an email after signup." No retries, dies with the process. Don't trust it for anything important.
2. **A real queue** — Arq (Redis-backed, async-native), Dramatiq, Celery. Use this for important async work (payments, emails to thousands of users, image processing).
3. **Postgres-backed queue** — `pg-boss` style, using `SELECT ... FOR UPDATE SKIP LOCKED`. Fine if you already have Postgres and don't want another piece of infrastructure.

```python
# app/api/v1/orders.py
from fastapi import BackgroundTasks
from app.workers.email import send_order_confirmation

@router.post("/orders", response_model=OrderPublic)
async def create_order(payload: OrderCreate, current: CurrentUser, db: DbSession,
                       bg: BackgroundTasks):
    order = await OrderService(db).create(current.id, payload)
    bg.add_task(send_order_confirmation, order.id)  # cheap, fine
    return order
```

## Testing

Use `pytest` + `pytest-asyncio` + `httpx.AsyncClient`. Run against a real Postgres (Docker, testcontainers) — not SQLite. SQLite lies about Postgres behavior in many subtle ways.

```python
# tests/conftest.py
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.base import engine, SessionLocal, Base
from app.api.deps import get_session as real_get_session

@pytest_asyncio.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client(db):
    async def override():
        yield db
    app.dependency_overrides[real_get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

# tests/test_users.py
async def test_create_and_fetch(client):
    resp = await client.post("/api/v1/users", json={
        "email": "a@example.com", "display_name": "A", "password": "x" * 12,
    })
    assert resp.status_code == 201
```

The test layout that scales: pytest fixtures for `db`, `client`, `auth_client(user)`. Tests express scenarios in the language of the API, not the ORM.

For external HTTP, use `respx` to intercept `httpx` calls. For time, use `freezegun` or `time-machine`. For property tests, `hypothesis` shines on parsing/validation logic.

## Observability

Production minimum:

- **Structured logs** — JSON, one event per line. `structlog` is the standard. Every request gets a `request_id`. Every log line includes it.
- **Metrics** — Prometheus exposition via `prometheus-fastapi-instrumentator` (RPS, latency histograms, in-flight, error counts) plus app-specific business metrics.
- **Tracing** — OpenTelemetry. The `opentelemetry-instrumentation-fastapi` package auto-instruments routes; add SQLAlchemy and httpx instrumentation for end-to-end traces.
- **Healthchecks** — `/healthz` (process alive) and `/readyz` (DB reachable). Keep them cheap.

```python
import logging
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()
```

## Deployment

- **ASGI server: Uvicorn behind a process manager.** Either `uvicorn` directly with `--workers N` (relies on uvicorn's process management) or `gunicorn -k uvicorn.workers.UvicornWorker -w N`. One worker per CPU core for CPU-bound, more for I/O-bound.
- **Don't run with `--reload` in production.** It's a development convenience.
- **Reverse proxy** (Nginx, Caddy, or your platform's ingress) handles TLS, gzip/brotli, static files, request size limits, and rate limiting.
- **`docs_url=None` or auth-gated** in production unless your API is public.
- **Environment-driven config**, no .env files in the image. Inject via the platform's secret manager.
- **Graceful shutdown** — SIGTERM → stop accepting connections → finish in-flight → exit. Uvicorn handles this if you don't fight it.

## Performance — what actually matters

Profile before optimizing. Once you do:

1. **Database is almost always the bottleneck.** Slow query log + `pg_stat_statements`. See the `postgresql` skill.
2. **N+1 queries.** Eager-load relationships. Log SQL in development.
3. **Synchronous I/O in async handlers.** Audit with `asyncio` debug mode and friends.
4. **Pydantic v2 is fast — but huge response payloads still serialize slowly.** Paginate. Don't return 10K objects.
5. **JSON encoding** — `orjson` via `fastapi.responses.ORJSONResponse` is the default for performance-sensitive endpoints.

## Anti-patterns

- Returning ORM objects directly (leaks fields, breaks contracts).
- Putting business logic in route functions (not testable without HTTP).
- Reusing one Pydantic model for input and output (different fields needed).
- Sync ORM calls in `async def` (blocks the loop).
- Ignoring `expire_on_commit=False` on the async session (objects become unusable after commit).
- Catching all exceptions in routes (mask bugs, mangle 500s).
- `Depends` everywhere, even when constructing the object is trivial — don't over-engineer.
- Custom auth middleware before trying the standard OAuth2 patterns.
- Using FastAPI for server-rendered HTML — that's not what it's for.