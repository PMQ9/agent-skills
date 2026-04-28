---
name: frontend-react-next
description: Use this skill for React and Next.js work — components, hooks, state, context, suspense, error boundaries, server components vs client components, App Router, Pages Router, route handlers, server actions, layouts, parallel/intercepting routes, middleware, caching (`fetch` cache, `unstable_cache`, `revalidatePath`, `revalidateTag`), data fetching, form handling, streaming, edge vs node runtime, image optimization, React Compiler, TanStack Query, Zustand, jotai, React Hook Form, Tailwind in React, testing with Vitest/Testing Library/Playwright, debugging hydration mismatches, and shipping production React apps. Trigger this whenever the codebase shows JSX, `next.config`, `app/` or `pages/` directories, `"use client"`, `"use server"`, or the user mentions React, Next, RSC, hooks, or component patterns.
---

# React & Next.js

React in 2026 is two languages sharing a syntax: **server components** that render once on the server and ship as serialized output, and **client components** that hydrate and run reactively in the browser. Next.js (App Router) is the most common production environment for both. Most "React is confusing now" complaints trace back to not having the server/client split clearly in mind. Get that right first; everything else follows.

## The mental model

```
[ Server: RSC tree ] ──serialize──> [ Wire format ] ──hydrate──> [ Client: interactive tree ]
        │                                                              │
        ├── Async, runs once per request (or build)                    ├── Reactive, lives in browser
        ├── Can fetch directly, query DB, read env                     ├── Has hooks, state, effects
        ├── Cannot use useState, useEffect, browser APIs               ├── Cannot directly query DB
        └── Default in App Router                                      └── Marked with `"use client"`
```

The seam is `"use client"`. Crossing it has rules:

- A server component can render a client component (passes props through serialization — props must be serializable: no functions, no class instances, no symbols).
- A client component cannot import a server component, but can **receive one as `children`** or via props from a server parent. This is the pattern: keep `"use client"` islands at the leaves; pass server-rendered content into them as `children`.
- `"use server"` marks a **server action** — a function callable from the client that runs on the server. Different feature than `"use client"`. Don't conflate them.

## When to reach for which

| Need | Use |
|---|---|
| Static or mostly-static page | Server component, default. |
| Data fetching for the page | Server component with `await fetch(...)` or direct DB call. |
| Anything with `useState`, `useEffect`, `onClick`, browser APIs | Client component. |
| Form submission to a backend | Server action (`"use server"`) or route handler. |
| Long-running webhook receiver, third-party callbacks | Route handler (`app/api/.../route.ts`). |
| Auth-aware redirect | Server component or middleware. |
| Real-time updates (websockets, SSE) | Client component. |

The instinct to slap `"use client"` on the root and be done with it works — and gives up most of what App Router offers (smaller JS, server-side data, streaming). Resist it. Push interactivity to the leaves.

## App Router structure

```
app/
  layout.tsx              # root layout, must have <html><body>
  page.tsx                # /
  loading.tsx             # streamed fallback for this segment
  error.tsx               # error boundary, must be "use client"
  not-found.tsx           # 404
  students/
    layout.tsx            # nested layout, persists across nav within /students/*
    page.tsx              # /students
    [id]/
      page.tsx            # /students/:id
      loading.tsx
    @modal/               # parallel route slot
      (...)login/
        page.tsx          # intercepting route
  api/
    students/
      route.ts            # GET, POST, etc. handlers
```

A few load-bearing things:

- **Layouts persist** across navigation within their segment. State in client components inside a layout survives child navigation. This is what makes nested layouts useful — sidebars, tabs, anything you don't want to remount.
- **`loading.tsx`** wraps `page.tsx` in a Suspense boundary. As soon as the layout is ready, the user sees the layout + the loading fallback while the page streams.
- **`error.tsx`** is an error boundary. It must be a client component (the only way React error boundaries work).
- **Parallel routes** (`@slot`) and **intercepting routes** (`(.)foo`) are powerful but easy to over-use. Reach for them when you need a modal that has its own URL, or two independent panels. Otherwise, plain nested layouts are clearer.

## Server components: data fetching

```tsx
// app/students/[id]/page.tsx
export default async function StudentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const student = await getStudent(id);   // direct DB or fetch — runs on server
  return <StudentDetails student={student} />;
}
```

Things that work in server components and don't in client components:

- `await` directly in the component body.
- Reading env vars, secrets, files, databases.
- Importing server-only libraries (Prisma, Drizzle, AWS SDK).

Mark server-only modules with `import "server-only"` at the top. If anyone tries to import that module from a client component, the build fails. The mirror is `import "client-only"`.

## Caching and revalidation in Next.js

This is where production apps trip over themselves. Next.js layers four caches:

1. **`fetch` cache** — by default, `fetch()` in a server component is cached. Pass `cache: 'no-store'` or `next: { revalidate: 60 }` to control. Off by default in Next 15+ for `fetch`; check your version.
2. **Data cache (`unstable_cache`)** — wrap arbitrary async functions to memoize across requests. Keyed and tagged.
3. **Full-route cache** — fully static pages get cached at build/ISR time.
4. **Router cache** — client-side, prefetched route segments.

To invalidate:

- `revalidatePath('/students')` — drops the cache for a route.
- `revalidateTag('students')` — drops everything tagged `students` (set tag at the fetch level).
- `revalidate` export from a page — sets max age for ISR.

Pattern that works well:

```ts
// fetch with a tag
const data = await fetch(url, { next: { tags: ['students'] } });

// in a server action that mutates students
'use server';
export async function deleteStudent(id: string) {
  await db.students.delete(id);
  revalidateTag('students');
}
```

Don't fight the cache. Read [the official docs section on caching](https://nextjs.org/docs) for your specific Next version, because behavior has changed across 13 → 14 → 15. Defaults flipped in Next 15.

## Server actions

```tsx
// app/students/new/page.tsx
import { createStudent } from './actions';

export default function NewStudentPage() {
  return (
    <form action={createStudent}>
      <input name="name" required />
      <button type="submit">Create</button>
    </form>
  );
}

// app/students/new/actions.ts
'use server';
import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

export async function createStudent(formData: FormData) {
  const parsed = StudentSchema.safeParse({
    name: formData.get('name'),
  });
  if (!parsed.success) return { error: parsed.error.format() };

  const student = await db.students.create(parsed.data);
  revalidatePath('/students');
  redirect(`/students/${student.id}`);
}
```

Server actions are just RPC with React-flavored ergonomics. Treat them like API endpoints:

- **Always validate input** at the boundary (Zod, Valibot). The client is untrusted, even when the call looks like a function call.
- **Always check authz** inside the action. The fact that the action is in your codebase doesn't authorize the caller.
- **Return serializable values.** Errors as objects, not thrown — or use error boundaries deliberately.
- **Don't leak server stack traces** to the client. In prod Next.js redacts these by default; don't undo that.

Pair with `useFormState` / `useActionState` and `useFormStatus` for pending UI without writing any client-side fetch boilerplate.

## Middleware

Runs at the edge before any rendering. Use for:

- Auth gates that redirect unauthenticated users.
- Locale detection / redirect.
- A/B test bucketing.
- Rewrites for legacy paths.

Don't use it for:

- Heavy work. It runs on every matched request.
- Reading the request body. You can't.
- Database queries. The edge runtime is severely limited.

```ts
// middleware.ts
export const config = { matcher: ['/dashboard/:path*'] };

export function middleware(req: NextRequest) {
  const session = req.cookies.get('session')?.value;
  if (!session) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('returnTo', req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
}
```

## Hooks: the real ones

A few hooks people misuse, and the corrected mental model:

### `useEffect`

If you reach for `useEffect`, ask first: is this a side effect outside React, or am I trying to derive state? **Most `useEffect` calls in app code are derivations and should be removed.**

```tsx
// Bad: derived state via useEffect
const [fullName, setFullName] = useState('');
useEffect(() => setFullName(`${first} ${last}`), [first, last]);

// Good: derived during render
const fullName = `${first} ${last}`;
```

```tsx
// Bad: fetching in useEffect
useEffect(() => {
  fetch(`/api/students/${id}`).then(r => r.json()).then(setStudent);
}, [id]);

// Good: a query cache
const { data: student } = useQuery({
  queryKey: ['student', id],
  queryFn: () => fetch(`/api/students/${id}`).then(r => r.json()),
});
```

Legitimate `useEffect`: subscribing to a non-React thing (DOM event on `document`, a websocket, an external store). For external stores specifically, use `useSyncExternalStore`, not `useEffect` + `useState`.

### `useMemo` / `useCallback`

Don't apply these by default. They have a cost (the dependency array, the closure, the ref). Apply them when:

- A child is wrapped in `memo` and you need its props to be referentially stable.
- The computation is genuinely expensive (rare).
- A `useEffect` depends on a derived value and you want to control re-runs.

Otherwise: render is cheap, allocations are cheap, just inline it. With **React Compiler** stable in 2026, the calculus changes further: enable it and most of these hand-tuned memos become unnecessary. Profile before pre-optimizing.

### `useState` initializer

```tsx
// Bad: expensive call on every render
const [tree] = useState(parseHugeBlob(blob));

// Good: lazy initializer, called once
const [tree] = useState(() => parseHugeBlob(blob));
```

Same for `useRef` initial values when they're expensive (use a getter or a ref-init pattern).

### `useReducer`

Reach for `useReducer` over `useState` when state transitions are non-trivial — a state machine with multiple actions, or where the next state depends on multiple parts of current state. The reducer keeps the transition logic in one place rather than scattered across handlers.

## State management: the real shape

For a typical Next.js app, the state landscape decomposes like this:

| Kind | Tool |
|---|---|
| Server state (data from your API) | TanStack Query, or RSC + `revalidate*` for full-stack Next. |
| URL state (filters, pagination, selected tab) | Search params. `nuqs` for ergonomics. |
| Local component state | `useState` / `useReducer`. |
| Cross-component UI state (theme, sidebar, toasts) | Zustand, jotai, or Context for small/static cases. |
| Form state | React Hook Form (most apps), or built-in form actions for server-action-shaped flows. |

**Redux is rarely the right answer for new apps in 2026.** It was a good answer to questions we no longer have. If you're considering it, you almost certainly want TanStack Query for server state + Zustand/jotai for the rest.

Context is a tool for prop-drilling avoidance, **not a state manager**. Context re-renders all consumers on every value change. For frequently-updated state, use a real store. Context is great for stable values: theme object, user object, locale.

## Forms: React Hook Form + Zod

```tsx
'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const Schema = z.object({
  name: z.string().min(1, 'Name required'),
  email: z.string().email(),
});
type FormValues = z.infer<typeof Schema>;

export function StudentForm({ onSubmit }: { onSubmit: (v: FormValues) => Promise<void> }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(Schema) });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('name')} aria-invalid={!!errors.name} />
      {errors.name && <p role="alert">{errors.name.message}</p>}
      <input {...register('email')} type="email" aria-invalid={!!errors.email} />
      {errors.email && <p role="alert">{errors.email.message}</p>}
      <button disabled={isSubmitting}>Submit</button>
    </form>
  );
}
```

Use the same Zod schema on the server for the action / route handler. Single source of truth for shape and validation.

## Error boundaries and Suspense

`app/error.tsx` catches render errors per route segment. It must be a client component. It receives `error` and `reset` props. Show a useful message and a retry.

`app/global-error.tsx` is the last-resort outer boundary; it replaces the entire layout including `<html>` and `<body>`.

Suspense lets you stream:

```tsx
// app/students/page.tsx
import { Suspense } from 'react';

export default function Page() {
  return (
    <>
      <h1>Students</h1>
      <Suspense fallback={<StudentListSkeleton />}>
        <StudentList />
      </Suspense>
      <Suspense fallback={<StatsSkeleton />}>
        <Stats />
      </Suspense>
    </>
  );
}
```

The header renders immediately. Each Suspense boundary streams in independently. This is the streaming model — cheap and effective; reach for it when a page has a fast part and a slow part.

## Hydration mismatches

Symptom: warning about "Hydration failed because the server-rendered HTML didn't match the client." Causes:

- Rendering `Date.now()`, `Math.random()`, or anything time-dependent in the initial render. Different on server and client.
- Reading `localStorage` or `window` during render.
- Locale-sensitive formatting that differs between server (UTC) and client (user TZ).
- HTML that's invalid by browser parsing rules — e.g., `<p><div></div></p>` (browsers split it).
- Browser extensions injecting attributes (frustratingly common, mostly safe to suppress with `suppressHydrationWarning` on the affected node).

Fix it correctly:

```tsx
'use client';
import { useEffect, useState } from 'react';

export function ClientOnlyTime() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  if (!now) return null;
  return <time>{now.toLocaleString()}</time>;
}
```

Or render the dynamic part only on the client via `dynamic(() => import(...), { ssr: false })`.

## Image, link, font: the Next built-ins

- **`<Image>`** — handles `srcset`, lazy loading, blur placeholders, AVIF/WebP, prevents CLS via required `width`/`height`. Use it.
- **`<Link>`** — automatic prefetching of route data on hover/viewport. Use for internal navigation; plain `<a>` for external.
- **`next/font`** — self-hosts Google Fonts at build time, no FOUT, no extra request. Use it.

## Testing

Three layers, mostly:

| Layer | Tool | What |
|---|---|---|
| Unit | Vitest | Pure functions, hooks (with `renderHook`), small components. Fast. |
| Component | Vitest + Testing Library | Rendered components, user-event simulation. |
| E2E | Playwright | Real browsers, real navigation, real fixtures. |

Testing Library principles still apply: query by accessible role/name, not by test-id. If you can't query a button by `getByRole('button', { name: 'Save' })`, your button isn't accessible — and the test is finding the same gap a screen reader user would.

For server components and server actions, test them like async functions — call them with a mocked db/env, assert the return. For full-stack flows, Playwright spinning up the actual app catches hydration / cache / route-handler bugs that nothing else does.

## Performance specifics for React/Next

The general perf advice in `frontend-development` applies. React/Next-specific levers:

- **Move work to the server.** A list rendered in a server component is HTML on the wire, not JSX + data + React on the wire.
- **Don't `"use client"` the whole tree.** Each `"use client"` boundary is a chunk in the JS bundle.
- **Dynamic import** rich client-only widgets: `const Editor = dynamic(() => import('./Editor'), { ssr: false });`.
- **Profile with the React DevTools profiler.** Look for renders triggered by parent re-renders that didn't actually change anything for the child — those are the `memo` + stable-callback opportunities.
- **Bundle-analyze.** `@next/bundle-analyzer`. Surprises will be 90% of your wins.

## Auth in Next

The reasonable choices in 2026:

- **NextAuth/Auth.js** — full-featured, providers galore, has rough edges in App Router but works.
- **Clerk, WorkOS, Stytch, Auth0** — managed, fast to ship, costs money.
- **Roll your own** with a session library (`lucia` until it was sunset; `iron-session`, `oslo`, or build on `jose`) — for full control and when your auth requirements don't fit a vendor's mold.

Keep session state in **HTTP-only cookies**. Don't put JWTs in `localStorage`. Validate the session in middleware for whole-app gating, and again in server components / actions / route handlers for resource-level checks. Defense in depth — middleware can be bypassed in some configurations; the resource-level check is the real authorization.

## Common bugs and their fixes

- **Stale closure in `useEffect`** — capture in a ref or use the functional update form.
- **Infinite render loop** — usually `setState` during render, or an effect whose deps include something it sets.
- **"Cannot update a component while rendering a different component"** — same family of bug. Hoist the state, or schedule with `queueMicrotask`/`setTimeout` if it's truly async.
- **Hydration mismatch with date/time** — render on the client only.
- **`useEffect` running twice in dev** — Strict Mode is doing its job. Make effects idempotent. This is not a bug.
- **Server component imports failing in client component** — restructure so the server component is passed as `children`.
- **`fetch` not caching as expected** — Next 15+ changed defaults. Specify `cache:` and `next:` explicitly.
- **`revalidatePath` doing nothing** — usually a wrong path, or the path doesn't match how the page is segmented. Try `revalidateTag` keyed off the data instead.
- **Server action returning a non-serializable value** — Date objects do work; functions, classes, Symbols don't. Stringify or restructure.

## Common anti-patterns

- `"use client"` at the root of `app/layout.tsx`. You just opted out of RSC entirely.
- Calling `fetch` inside a `useEffect` for data the page needs immediately. Fetch in the server component instead, or use a query library that handles loading/error/cache.
- A 4,000-line component because nobody felt empowered to split it.
- Prop-drilling 6 levels because Context "felt heavy." It isn't, for stable values.
- Hand-rolled global stores with `useState` + Context for frequently-changing data. The whole tree re-renders on every change.
- Server actions without input validation. RPC with no auth and no validation is just a vulnerability.
- `dangerouslySetInnerHTML` on user-supplied content without sanitization. Use a sanitizer (DOMPurify) or, better, render it as React.
- Catching every error in a try/catch and returning `null`, hiding bugs from your error tracker.
- `key={index}` on a list of items that reorder. Use a stable id.
- Forgetting that `params` and `searchParams` in Next 15+ are Promises. Await them.
- Mixing TanStack Query and React Query (older name). Pick one version, stay on it.
- Redux for everything, including server data. Use a query cache.

## A reasonable Next.js project skeleton

```
app/
  (marketing)/             # route group, no URL segment
    layout.tsx
    page.tsx
  (app)/                   # authenticated app
    layout.tsx
    students/
      page.tsx
      [id]/page.tsx
      actions.ts
  api/
    webhooks/
      stripe/route.ts
  layout.tsx               # root
  error.tsx
  not-found.tsx
components/                # cross-feature, app-aware
ui/                        # design system
features/                  # vertical slices
lib/
  db/
  auth/
middleware.ts
next.config.ts
tsconfig.json
```

Pin your Node version in `.nvmrc` / `package.json` `engines`. Pin React + Next versions exactly. Lockfile committed. CI runs `next build` on every PR.
