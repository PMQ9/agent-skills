---
name: go-backend
description: Use this skill for any work involving Go (Golang) backend development — including writing HTTP/gRPC services, designing project layout, working with goroutines / channels / context, error handling, the standard library's net/http, popular routers (chi, echo, gin, fiber), database access (database/sql, sqlx, sqlc, pgx, GORM), structured logging with slog, configuration, testing (table-driven tests, httptest, testify, mocks), benchmarking, profiling with pprof, build/release, or reviewing Go code for idiom and correctness. Trigger on .go files, go.mod, "Go service", "goroutine", "channel", "context.Context", "should I use a pointer", "error wrapping", "interface here?". Also trigger when a user is choosing a language for a backend service and Go is one of the options.
---

# Go Backend Development

Go is small on purpose. The language has fewer features than its peers, and that's the point: less surface area, more uniformity, code that an unfamiliar reader can pick up quickly. Working *with* Go's grain — not against it, not pretending it's Java or Rust — is the difference between a maintainable service and a fight.

The orienting principles, repeated by long-time Go developers until they sound trite (because they're true):

- **Clear is better than clever.**
- **Errors are values.** Handle them.
- **Don't communicate by sharing memory; share memory by communicating.** (And actually, when in doubt, just use a mutex — channels aren't always the answer.)
- **A little copying is better than a little dependency.**
- **Accept interfaces, return concrete types.**

## Project layout

For a typical service, this works:

```
myservice/
├── cmd/
│   └── myservice/
│       └── main.go         # tiny: parse flags/config, wire dependencies, run
├── internal/               # everything not consumed externally goes here
│   ├── http/               # HTTP handlers, middleware
│   ├── grpc/               # gRPC handlers (if applicable)
│   ├── service/            # business logic; depends only on domain types
│   ├── store/              # persistence (DB, cache, object store)
│   ├── domain/             # types and interfaces shared across layers
│   └── config/
├── migrations/             # SQL migrations, if you own the DB
├── api/                    # OpenAPI/proto definitions
├── go.mod
└── go.sum
```

A few specifics:

- **`internal/`** is enforced by the compiler — packages there cannot be imported by external modules. Use it generously; resist creating a public API surface you don't intend to support.
- **No `pkg/` shrine** unless you actually publish reusable code. The `pkg/` convention is overused; for a single application, `internal/` is enough.
- **`main.go` should be short** — wire-up and lifecycle, no business logic. If `main` is 500 lines, you've put logic where it doesn't belong.
- **Don't pre-split into microscopic packages.** "One package per thing" leads to import cycles and contortions. Split when packages are genuinely independent.

## Configuration

Read config from environment variables (12-factor) for production, with optional flag overrides. A small library like `kelseyhightower/envconfig`, `caarlos0/env`, or `spf13/viper` (heavier) is fine; for very small services, just `os.Getenv` and explicit parsing.

```go
type Config struct {
    HTTPAddr     string        `env:"HTTP_ADDR" envDefault:":8080"`
    DatabaseURL  string        `env:"DATABASE_URL,required"`
    LogLevel     slog.Level    `env:"LOG_LEVEL" envDefault:"info"`
    ShutdownWait time.Duration `env:"SHUTDOWN_WAIT" envDefault:"30s"`
}
```

Validate at startup. A service that boots with a missing config and fails on first request is worse than one that fails to start.

## HTTP servers

The standard library's `net/http` is genuinely good. Since Go 1.22, the default mux supports method-and-path routing (`mux.HandleFunc("GET /users/{id}", ...)`) which removes much of the historical reason to reach for a router.

When you do want a router, **`go-chi/chi`** is the idiomatic choice — it's `http.Handler`-compatible all the way down, has solid middleware composition, and nothing magical. `gin` and `fiber` are popular but have their own context types and idioms; they're fine, just less standard-library-flavored.

### A production-grade HTTP server skeleton

```go
func main() {
    cfg := mustLoadConfig()
    logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: cfg.LogLevel}))
    slog.SetDefault(logger)

    db := mustOpenDB(cfg.DatabaseURL)
    defer db.Close()

    svc := service.New(db, logger)
    handler := httpapi.NewRouter(svc, logger)

    srv := &http.Server{
        Addr:              cfg.HTTPAddr,
        Handler:           handler,
        ReadHeaderTimeout: 5 * time.Second,
        ReadTimeout:       15 * time.Second,
        WriteTimeout:      30 * time.Second,
        IdleTimeout:       120 * time.Second,
    }

    // Run + graceful shutdown
    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer stop()

    go func() {
        logger.Info("listening", "addr", cfg.HTTPAddr)
        if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
            logger.Error("listen failed", "err", err)
            stop()
        }
    }()

    <-ctx.Done()
    logger.Info("shutting down")
    shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownWait)
    defer cancel()
    if err := srv.Shutdown(shutdownCtx); err != nil {
        logger.Error("shutdown error", "err", err)
    }
}
```

Notes on the timeouts: **`ReadHeaderTimeout` is the one most people miss** and is the one that protects you from Slowloris-style attacks. `WriteTimeout` is a hard ceiling on a single response; if you stream large bodies, you may need to disable it on those routes.

### Handler shape

A handler that returns an error and is wrapped by a small adapter is much more pleasant to write than naked `http.HandlerFunc` everywhere:

```go
type apiHandler func(w http.ResponseWriter, r *http.Request) error

func (h apiHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if err := h(w, r); err != nil {
        renderError(w, r, err)  // map err -> status code + body, log
    }
}
```

This lets you write `return ErrNotFound` instead of remembering to `return` after `http.Error(...)` everywhere. The error-renderer is the single place that maps domain errors to status codes.

## Errors

Go errors are values. The patterns that have stabilized:

- **Return errors, don't panic.** Panic is for programmer bugs (nil pointer, index out of range), not expected failure modes.
- **Wrap with context** when crossing a layer: `fmt.Errorf("fetching user %s: %w", id, err)`. The `%w` verb preserves the wrapped error so `errors.Is` and `errors.As` work.
- **Sentinels for known conditions:** `var ErrNotFound = errors.New("not found")`. Callers check with `errors.Is(err, ErrNotFound)`.
- **Typed errors for structured data:** when you need to carry details (a field name, an HTTP status), define a struct that implements `error`. Callers check with `errors.As`.
- **Don't log and return.** Log at the boundary (the HTTP handler, the queue worker), not at every level. Otherwise the same error appears five times in logs.
- **`errors.Join` (Go 1.20+)** for multi-error scenarios — concurrent operations, validation that wants to report multiple problems.

```go
func (s *Service) GetUser(ctx context.Context, id string) (*User, error) {
    u, err := s.store.UserByID(ctx, id)
    if err != nil {
        if errors.Is(err, store.ErrNotFound) {
            return nil, ErrUserNotFound
        }
        return nil, fmt.Errorf("get user %s: %w", id, err)
    }
    return u, nil
}
```

A common mistake: panic'ing on errors that "shouldn't happen." If it shouldn't happen, return the error and let the caller decide. Panic should be reserved for invariants — situations where the program is in an unrecoverable state.

## Context

`context.Context` is how Go propagates cancellation, deadlines, and request-scoped values through the call chain.

- **Pass `ctx` as the first argument** to any function that does I/O, touches a database, or might block.
- **Don't store contexts in structs.** They're per-request. The exception: storing a parent context for a long-running goroutine, where it's clearly the lifetime of the goroutine.
- **Don't pass `nil` contexts.** Use `context.Background()` (top-level, no parent) or `context.TODO()` (placeholder when you haven't decided).
- **Cancel contexts you create.** `ctx, cancel := context.WithCancel(parent); defer cancel()`. Even when you've returned successfully — unfreed cancel funcs are a slow leak.
- **Use `context.Value` sparingly.** It's untyped and discoverable only by reading code. Reasonable for things genuinely orthogonal to function signatures (request ID, trace span, auth principal). Not a way to avoid passing arguments.

## Concurrency

The famous Go primitives: goroutines and channels. The pragmatic advice:

- **A goroutine is cheap, but not free.** Spawning unbounded goroutines per incoming work item is a fast path to "my service got stuck under load." Use a worker pool, a semaphore, or `errgroup.Group.SetLimit`.
- **Every goroutine needs a known stop condition.** A goroutine without an exit path is a goroutine leak. Tie its lifetime to a context, a closed channel, or a `sync.WaitGroup` you actually wait on.
- **Mutexes are fine.** "Channels for orchestration, mutexes for shared state" is a useful heuristic. A mutex protecting a map is shorter, faster, and clearer than a goroutine-with-channel pattern.
- **`sync.RWMutex` is rarely worth it** for short critical sections — the bookkeeping overhead can exceed the gain. Profile before reaching for it.
- **`errgroup`** (`golang.org/x/sync/errgroup`) is the right pattern for "do these N things concurrently, fail if any fails":

```go
g, ctx := errgroup.WithContext(ctx)
g.SetLimit(8)
for _, id := range ids {
    id := id  // pre-Go 1.22
    g.Go(func() error {
        return process(ctx, id)
    })
}
if err := g.Wait(); err != nil { return err }
```

(Go 1.22+ removed the loop-variable capture footgun, so `id := id` is no longer needed in modern code.)

### Channel patterns that work

- **Signaling done:** `done chan struct{}` closed when work finishes. `<-done` blocks until closed.
- **Fan-out / fan-in:** N workers reading from one input channel, all writing to one output channel.
- **Bounded buffer:** `make(chan T, capacity)` for back-pressure.
- **Single-producer-single-consumer for hand-off** is the cleanest channel use.

### Patterns that don't

- Channels as event buses across many components — gets tangled.
- Channels for fine-grained mutual exclusion — use a mutex.
- Closing a channel from multiple goroutines — panic. Use `sync.Once` if you must.

## Databases

`database/sql` is the standard interface. On Postgres, **`pgx`** (specifically `pgx/v5`) is the best driver — it has a native interface that's faster, plus a `database/sql`-compatible mode. Use the native interface when you can.

For SQL-with-types, the field has stabilized:

- **`sqlc`** generates Go code from SQL queries. You write the query, it generates the function. This is the cleanest path: type-safe, no runtime reflection, no ORM mysticism. Strongly recommended for greenfield work.
- **`sqlx`** extends `database/sql` with named parameters and struct scanning. Useful if you want a thin layer of convenience without code generation.
- **`pgx` directly** is fine for small services or hot paths.
- **GORM** is popular but has trade-offs: `Save` ambiguity, surprising N+1s, magic. Acceptable on small projects; on larger ones, the abstraction tax compounds. If a team is already using it, that's not a fight worth picking; for new services, prefer `sqlc`.

### Connection pool sizing

```go
db.SetMaxOpenConns(25)
db.SetMaxIdleConns(25)
db.SetConnMaxLifetime(5 * time.Minute)
db.SetConnMaxIdleTime(5 * time.Minute)
```

`MaxOpenConns` is the cap. Total across all instances must fit under the database's `max_connections`. `ConnMaxLifetime` matters for setups behind PgBouncer or load balancers that age out connections — long-lived idle conns get rudely closed otherwise.

### Transactions

Pass the transaction (or an interface that abstracts `*sql.Tx` and `*sql.DB`) into your store methods, so callers control the transaction boundary:

```go
type DB interface {
    QueryContext(ctx context.Context, q string, args ...any) (*sql.Rows, error)
    ExecContext(ctx context.Context, q string, args ...any) (sql.Result, error)
}
```

Both `*sql.DB` and `*sql.Tx` satisfy this. Service-layer code starts a tx, passes the tx into stores, commits or rolls back.

## Logging — `log/slog`

As of Go 1.21, `log/slog` is the standard library's structured logger. Use it.

```go
slog.Info("order.created", "order_id", id, "user_id", uid, "amount_cents", cents)
```

- JSON handler for production, text handler for local.
- `slog.With` to bind common fields per request — or, idiomatically, attach a logger to the request context.
- Set the trace_id / request_id field on the logger early in middleware so every line has it.
- Avoid `fmt.Sprintf` into log messages; pass key-values so the structure is searchable.

## Testing

Go testing is intentionally minimal: `*testing.T`, `t.Run`, `t.Helper`, table-driven tests. Rich frameworks aren't needed and frequently obscure things.

```go
func TestParse(t *testing.T) {
    cases := []struct {
        name    string
        input   string
        want    Result
        wantErr bool
    }{
        {"empty", "", Result{}, true},
        {"basic", "x=1", Result{X: 1}, false},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got, err := Parse(tc.input)
            if (err != nil) != tc.wantErr {
                t.Fatalf("err = %v, wantErr %v", err, tc.wantErr)
            }
            if got != tc.want {
                t.Errorf("got %+v, want %+v", got, tc.want)
            }
        })
    }
}
```

- **`testify`** (`require`, `assert`) is fine and widely used. Don't need it, but it doesn't hurt.
- **`httptest.NewServer`** for HTTP-handler tests. Don't mock `http.Client`; spin up a server.
- **Mocks**: hand-written or generated by `mockery` / `moq`. Don't over-mock — prefer integration tests against a real Postgres in a container (`testcontainers-go`) for store layer code; unit tests with mocks for service-layer logic.
- **Golden files** for snapshot-style tests. `flag.Bool("update", ...)` to regenerate.
- **`go test -race`** in CI. Always.

## Profiling and performance

Go's tooling is excellent.

- **`net/http/pprof`** — import for the side effect, mount under `/debug/pprof/`. Don't expose publicly. Gives you CPU, heap, goroutine, mutex, block, allocs profiles.
- **`go tool pprof`** to analyze. Top functions, flame graphs, peak allocations.
- **Benchmarks live next to tests:** `func BenchmarkX(b *testing.B)`. Run with `go test -bench=. -benchmem`. Use `b.ReportAllocs()`, `benchstat` to compare runs.
- **Allocations are usually the lever.** Reducing allocations almost always helps. Reuse buffers (`sync.Pool` for hot loops), preallocate slices, avoid `[]byte` ↔ `string` conversions in tight code.
- **Don't optimize without measuring.** Profile before; measure delta after. "I think this'll be faster" is wrong about half the time.

## Build and release

- **`CGO_ENABLED=0` static binaries** unless you genuinely need cgo (e.g., SQLite). Static binaries make container images trivial.
- **Multi-stage Dockerfile**, build in `golang:1.x` image, copy the binary into `gcr.io/distroless/static-debian12` or `scratch`. Final image is the binary plus `/etc/ssl/certs/ca-certificates.crt`. Often <20 MB.
- **`go build -ldflags="-s -w"`** to strip debug info; `-trimpath` to remove local paths from the binary. Embed version: `-ldflags="-X main.version=$GIT_SHA"`.
- **`go vet`** in CI. **`staticcheck`** in CI. **`golangci-lint`** as a curated bundle.

## API design

- **REST: predictable resources, status codes, pagination via cursors not offsets.** Cursors are stable under inserts; offsets are not.
- **gRPC** when you control both ends and want efficient binary protocols + streaming. Generate clients from `.proto`.
- **Both:** use **protobuf or OpenAPI as the source of truth**, generate the server stubs and the clients. Hand-keeping API definitions and code in sync is a recurring source of bugs.
- **Versioning:** `/v1/`, `/v2/` in the URL is fine and explicit. Don't break v1 once you've published it.

## Common pitfalls

- **Capturing a loop variable in a goroutine** before Go 1.22 — `for _, x := range xs { go func() { use(x) }() }` was wrong; needed `x := x`. Go 1.22 fixed this. If you support older Go, watch for it.
- **Nil interface vs interface containing nil pointer.** `var err error = (*MyErr)(nil); err != nil` is true and will surprise you. Return concrete `nil` for "no error."
- **Forgetting `defer cancel()`** when you create a context — context leak.
- **Forgetting `rows.Close()`** in `database/sql` — connection leak.
- **`json:"name,omitempty"` with `int`** treats `0` as "absent." For nullable ints, use `*int` or `sql.NullInt64`.
- **Time zones.** `time.Time` carries a location; equality and DB round-tripping care. Standardize on UTC for storage.
- **Maps are not safe for concurrent use.** A concurrent `map[K]V` with reads and writes is a runtime crash, not a benign race. Use `sync.Mutex` or `sync.Map` (the latter is for specific access patterns; default to a regular map + mutex).
- **Slices share backing arrays.** `s2 := s1[2:5]` writes to `s2[0]` mutate `s1[2]`. `append` *may* create a new array or may not. Be deliberate.
- **String concatenation in a loop** allocates O(n²). Use `strings.Builder`.

## Idiom checklist for code review

- Errors handled, wrapped with context, not silently swallowed.
- No `panic` in normal control flow.
- `context.Context` propagated through every call that does I/O.
- Goroutines have a clear stop condition.
- `defer` for cleanup (close, unlock, cancel) right after acquisition.
- Exported names have doc comments starting with the name.
- No `interface{}` / `any` without justification.
- Interfaces declared at the consumer (caller), not the producer.
- Tests are present, including for the unhappy path.
- `go vet` and `staticcheck` pass.
- No leaked file handles, DB rows, or HTTP response bodies (`defer resp.Body.Close()`).
