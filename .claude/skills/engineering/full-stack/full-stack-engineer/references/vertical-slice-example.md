# Worked example: one vertical slice, end to end

This makes the SKILL.md principles concrete: **one source of truth for the shape, parse at every boundary, test the seam.** The feature is deliberately tiny — *a signed-in user can create a note and see their notes* — so the structure, not the feature, is what shows through.

The stack here is illustrative: **TypeScript end to end** (Node API + React) with **Postgres** and a **shared Zod schema** in a monorepo package. The shape of the advice transfers to any stack — the section headers are the steps, whatever your languages. Where this stack would differ from yours, the comment says so.

## 0. The seam this slice has to get right

```
shared/  ← the contract lives here, imported by BOTH sides
  schema.ts
api/
  db/migrations/0001_notes.sql
  routes/notes.ts
  notes.test.ts
web/
  api-client.ts
  NotesPage.tsx
```

The whole point of the layout: `shared/schema.ts` is imported by the API *and* the web app, so there is exactly one definition of what a `Note` is. Change it and both sides fail to compile until they agree. (Not on a JS stack? The equivalent is OpenAPI/protobuf as the source of truth with generated types per language. The principle is identical: one definition, generated outward.)

## 1. Source of truth: the shared schema

```ts
// shared/schema.ts — imported by api/ and web/
import { z } from "zod";

// Input the client may send (no id, no timestamps — the server owns those)
export const CreateNote = z.object({
  title: z.string().min(1, "Title is required").max(200),
  body: z.string().max(10_000).default(""),
});
export type CreateNote = z.infer<typeof CreateNote>;

// The canonical Note as it crosses the wire
export const Note = z.object({
  id: z.string().uuid(),
  title: z.string(),
  body: z.string(),
  createdAt: z.string().datetime(), // ISO-8601 UTC string, never a Date over JSON
});
export type Note = z.infer<typeof Note>;

export const NoteList = z.object({
  items: z.array(Note),
  nextCursor: z.string().nullable(), // pagination from day one
});
```

`CreateNote` and `Note` are different on purpose: the client doesn't get to set `id` or `createdAt`. Modeling input and output as one type is a common seam bug (the client sends an `id`, the server trusts it).

## 2. Data layer: the migration

```sql
-- api/db/migrations/0001_notes.sql  (append-only; never edited after deploy)
CREATE TABLE notes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title       text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  body        text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT now()  -- timestamptz, not timestamp
);
-- The list query is "this user's notes, newest first" — index for it.
CREATE INDEX notes_user_created_idx ON notes (user_id, created_at DESC);
```

The `CHECK` and `NOT NULL` constraints are free correctness — the database refuses bad data even if a future code path forgets to validate. `timestamptz` stores UTC; the seam rule "store UTC, send ISO, format in the UI" starts here.

## 3. Backend: endpoint with validation and a typed error envelope

```ts
// api/routes/notes.ts
import { CreateNote, Note, NoteList } from "../../shared/schema";

// POST /api/notes  — create
router.post("/api/notes", requireAuth, async (req, res) => {
  // Parse at the boundary. Untrusted input becomes a typed value or a 422.
  const parsed = CreateNote.safeParse(req.body);
  if (!parsed.success) {
    return res.status(422).json({
      error: { code: "validation_error", message: "Invalid note",
               fields: parsed.error.flatten().fieldErrors },
    });
  }
  // req.user is set by requireAuth — authorization happened at the edge,
  // the domain below operates only on already-authorized input.
  const row = await db.one(
    `INSERT INTO notes (user_id, title, body) VALUES ($1, $2, $3)
     RETURNING id, title, body, created_at`,
    [req.user.id, parsed.data.title, parsed.data.body],
  );
  // Serialize to the contract. created_at (Date) → ISO string at the seam.
  const body: Note = { id: row.id, title: row.title, body: row.body,
                       createdAt: row.created_at.toISOString() };
  res.status(201).json(body);
});

// GET /api/notes  — list (paginated, scoped to the user)
router.get("/api/notes", requireAuth, async (req, res) => {
  const rows = await db.many(
    `SELECT id, title, body, created_at FROM notes
     WHERE user_id = $1 ORDER BY created_at DESC LIMIT 21`, [req.user.id]);
  const items = rows.slice(0, 20).map((r) => ({
    id: r.id, title: r.title, body: r.body, createdAt: r.created_at.toISOString(),
  }));
  const payload: NoteList = { items,
    nextCursor: rows.length > 20 ? items[items.length - 1].createdAt : null };
  res.json(payload);
});
```

Note the consistent error envelope (`{ error: { code, message, fields } }`), the `LIMIT 21`-to-detect-next-page pagination trick, and that authorization (`requireAuth` + scoping `WHERE user_id = $1`) lives at the edge, not in business logic.

## 4. The client: parse the response, don't trust it

```ts
// web/api-client.ts
import { CreateNote, Note, NoteList } from "../shared/schema";

export async function createNote(input: CreateNote, signal?: AbortSignal): Promise<Note> {
  const res = await fetch("/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(CreateNote.parse(input)), // validate before sending too
    credentials: "include", // send the HttpOnly session cookie
    signal,
  });
  if (!res.ok) throw await ApiError.from(res); // typed error, not stringly-typed
  return Note.parse(await res.json());          // PARSE — the response is a boundary
}

export async function listNotes(signal?: AbortSignal): Promise<NoteList> {
  const res = await fetch("/api/notes", { credentials: "include", signal });
  if (!res.ok) throw await ApiError.from(res);
  return NoteList.parse(await res.json());
}
```

`Note.parse(await res.json())`, never `(await res.json()) as Note`. If the API ships a breaking change, this throws *here*, loudly, instead of rendering `undefined` three components deep. The session rides in an `HttpOnly` cookie (`credentials: "include"`), not a token in `localStorage`.

## 5. The UI: loading, error, and empty are first-class

```tsx
// web/NotesPage.tsx — using a query cache (TanStack Query) for server state
function NotesPage() {
  const notes = useQuery({ queryKey: ["notes"], queryFn: ({ signal }) => listNotes(signal) });
  const create = useMutation({
    mutationFn: createNote,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notes"] }),
  });

  if (notes.isLoading) return <Spinner label="Loading notes" />;
  if (notes.isError)   return <ErrorState onRetry={() => notes.refetch()} />;
  if (notes.data.items.length === 0) return <EmptyState onCreate={create.mutate} />;

  return (
    <>
      <NoteForm onSubmit={create.mutate} pending={create.isPending}
                error={create.error} /> {/* server validation errors shown inline */}
      <ul>{notes.data.items.map((n) => <NoteRow key={n.id} note={n} />)}</ul>
    </>
  );
}
```

Four states handled explicitly: loading, error (with retry), empty (with a call to action), and populated. Server state lives in the query cache, not a global store. Validation errors from the 422 surface inline on the form, because the same Zod rules produced them.

## 6. Test the seam, not just the layers

The unit tests on validation are cheap and fine. The test that earns its keep for a full-stack engineer is the **integration test through the real boundary**: real HTTP, real database (in a container), real serialization.

```ts
// api/notes.test.ts — runs against a real Postgres via testcontainers
test("create then list returns the note in the contract shape", async () => {
  const agent = await signInTestUser();             // real auth, real cookie
  const created = await agent.post("/api/notes").send({ title: "Hello" });
  expect(created.status).toBe(201);
  Note.parse(created.body);                          // asserts the wire shape

  const list = await agent.get("/api/notes");
  const parsed = NoteList.parse(list.body);          // asserts the list contract
  expect(parsed.items[0].title).toBe("Hello");
  expect(parsed.items[0].createdAt).toMatch(/Z$/);   // came back as UTC ISO
});

test("rejects an empty title with a 422 and field errors", async () => {
  const agent = await signInTestUser();
  const res = await agent.post("/api/notes").send({ title: "" });
  expect(res.status).toBe(422);
  expect(res.body.error.fields.title).toBeDefined();
});
```

Parsing the response with the *same shared schema* inside the test means the test fails the instant the API drifts from the contract — the seam is guarded. One Playwright test then drives the real UI through "sign in → create a note → see it in the list" to cover the front half of the seam.

## 7. Ship it backward-compatibly

The migration runs as a gated deploy step *before* the new code starts serving. Because old and new code overlap during rollout:

- This first migration is additive (a new table), so it's safe — nothing old breaks.
- If a later change added a required `Note.color` field, the safe order is: (1) add the column nullable + start writing it, deploy; (2) backfill existing rows; (3) make the API return it and the client expect it; (4) only then enforce `NOT NULL`. Shipping the client's expectation before the API provides the field would 422 or render-error every user mid-deploy.

That backward-compatible discipline — for the database schema *and* the API contract — is the production half of "the data contract is the spine."
