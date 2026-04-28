---
name: mcp-server-design
description: Design and build Model Context Protocol (MCP) servers — choosing between tools, resources, and prompts; schema design that LLMs can actually use; error handling that produces recoverable failures; auth patterns; transport selection; pagination and large-output handling; and the security considerations specific to exposing tools to autonomous agents. Use this skill whenever the task involves building an MCP server, exposing functionality to Claude or another MCP client, debugging "the model isn't calling my tool" or "the model is calling my tool wrong," reviewing an MCP server design, or any work where the goal is letting an LLM interact with a system via MCP. Trigger on terms like "MCP," "Model Context Protocol," "MCP server," "MCP tool," "Anthropic connector," "expose this to Claude," and similar.
---

# MCP Server Design

The Model Context Protocol is a thin, well-specified protocol for exposing tools, data, and prompts to LLM clients. The protocol is the easy part. The hard part is designing servers that LLMs can actually use well — schemas that make sense to a model, errors it can recover from, and capability surfaces that match how agents actually decompose work. This skill covers the design choices that determine whether your MCP server is useful or merely present.

## The three primitives

MCP servers expose three kinds of things, and getting the choice right matters:

**Tools.** Functions the model can invoke. Side-effecting or computational. The model decides when to call them.

**Resources.** Data the model can read. URIs that the model (or the host application) can fetch. Static or parameterized. The model does not invoke them as actions; they're more like files.

**Prompts.** Templates the user (not the model) selects, which produce a starting message for the LLM. Useful for repeated workflows, less useful for autonomous agents.

The default mistake is to make everything a tool. Two clarifying questions:

- "Is this idempotent and side-effect-free, and is the model going to read it as data?" → Resource.
- "Does this take an action, return a computed result, or have side effects?" → Tool.
- "Is this a user-triggered workflow shortcut?" → Prompt.

When in doubt, prefer tools — they are the most universally supported primitive across MCP clients, and many clients today don't implement resources or prompts as fully. But if your "tool" is `get_documentation_page(slug)` and is purely a read, consider a resource. The model treats data fetching and action invocation differently in its planning; matching its expectations improves behavior.

## Tool design

Tools are an API contract between you and the LLM. The LLM is your user, reading your description, fitting your schema, recovering from your errors. Design for that user.

### Naming

Tool names should be:

- **Verb-led for actions, noun-led for queries.** `create_issue`, `send_email`, `list_users`, `get_user`. Consistency helps the model build a mental model of your surface.
- **Scoped.** `github_create_issue` is better than `create_issue` if the server exposes multiple namespaces or if the model is talking to multiple servers. Disambiguation in the name is free; ambiguity costs tool calls.
- **Specific over generic.** `search_codebase_by_symbol` beats `search` if the tool searches code. The model picks tools partly by name match to its current intent; specific names are easier to match.

Avoid: cute names ("ask_oracle"), abbreviations the model won't recognize ("mk_iss"), names that overlap with common functions ("execute", "run", "do").

### Descriptions

Tool descriptions are the most under-invested part of MCP servers. Write them like docstrings for an experienced engineer who has never seen your system before:

- **What it does.** One sentence, concrete.
- **When to use it.** Concrete situations where this is the right tool.
- **When not to use it.** Common mis-uses, especially the closest neighbors in your tool surface.
- **Examples.** Two or three input/output sketches for non-obvious cases.
- **Common errors and what they mean.** "Returns NOT_FOUND if the path doesn't exist; check `list_files` first if uncertain."

A good description is 100-300 words for a non-trivial tool. Models do not skim — longer, accurate descriptions improve tool-selection accuracy. The cost is one-time at protocol initialization; the win compounds across every call.

A test: hand the tool description to a developer who has never seen your service and ask them to write code that uses it correctly. If they can't, the model can't either.

### Input schemas

Use JSON Schema fully. Do not just declare types and stop.

- **Required vs optional.** Mark required fields required. The model respects this.
- **Descriptions on every property.** What is this field, what's a valid example, what's the unit (seconds vs ms, dollars vs cents).
- **Enums where applicable.** `priority: ["low", "medium", "high"]` is a constraint the model can satisfy. `priority: string` is a guess.
- **Constraints (min, max, pattern).** Use them. The model often respects them and the framework will reject invalid inputs before they reach you.
- **Defaults.** Document them in the description even if your validator applies them automatically.

Avoid:

- Free-text fields where structure exists. If the field is "list of file paths," make it `array of strings`, not `string of comma-separated paths`.
- Polymorphic fields. `value: object` that means different things based on a sibling `type` field is a footgun. The model will get the wrong shape sometimes. If you need polymorphism, expose multiple tools or use JSON Schema's `oneOf` with discriminators.
- Magic strings. `"flags": "VERBOSE,DEBUG,FOLLOW_LINKS"` should be an array of enums.

### Output schemas

MCP allows tools to declare structured output schemas in addition to (or instead of) free-text content. Use this whenever the result has structure.

Why: the client (and the model) can validate the result, and downstream tools can chain on specific fields. Free-text outputs are debuggable but not composable.

For tools that return both — a structured result and human-readable summary — emit both. The model uses the summary for reasoning and the structured form for chaining.

### Granularity

A common failure mode is a tool surface that is either too narrow or too wide.

Too narrow: one tool per database column. The model burns 40 calls to do what should be one query.

Too wide: a single `do_thing(action: str, params: object)` tool with twenty internal modes. Loses all the schema-level guidance the model needs to pick the right mode.

The right granularity matches the *unit of work* in the domain. For a calendar API: `list_events`, `create_event`, `update_event`, `delete_event` — four tools, each doing one thing well. Not `event_action(action, params)`, and not separate tools for `create_event_with_attendees` and `create_event_without_attendees`.

A useful heuristic: if two tools share most of their parameters and differ only in one boolean, merge them. If one tool's parameters are an enum that completely changes its behavior, split it.

### Errors

This is where most MCP servers degrade. The model cannot recover from errors it does not understand. Design error responses as carefully as success responses.

Error responses should include:

- **What went wrong.** "File not found at path 'foo.py'."
- **Why, if non-obvious.** "The path appears to be relative; this tool expects absolute paths."
- **What to try instead.** "Use `list_files` to see what's available, or pass an absolute path starting with `/`."
- **Whether to retry.** Distinguish transient errors (rate limit, network) from permanent (not found, permission denied) so the model knows whether retrying is sensible.

Example of a bad error: `"Error: 404"`.
Example of a good error: `"Error: file 'foo.py' not found in repository 'acme/widgets'. The repository contains: src/main.py, src/utils.py, tests/test_main.py. Did you mean 'src/main.py'? This is a permanent error; retrying will not help."`

Yes, the second is verbose. Yes, it costs tokens. Yes, it pays for itself the first time the agent recovers from a typo instead of looping.

## Resources

Resources are more like a filesystem than an API. They represent data the model (or the host) can read by URI. Examples: a wiki page, a code file, a row in a database, a calendar event.

Use resources when:

- The thing is read-only or read-mostly.
- The model would benefit from the host caching/displaying it.
- You want the host to manage subscription/freshness.

URI design: pick a scheme and stick to it. `wiki://team/onboarding`, `db://customers/123`, `file:///path/to/thing`. Make URIs predictable so the model can guess them from context (e.g., from a search result).

Resource templates allow parameterized URIs (`db://{table}/{id}`). Useful for letting the model construct URIs based on tool output.

A common pattern: a `search` tool returns URIs as part of its results; the host or model fetches the resource bodies on demand. This separates retrieval (small, fast) from full content access (large, lazy).

## Prompts

Prompts are user-facing templates. The user picks one (typically from a slash-command menu or similar UI) and the host expands it into messages.

Use prompts when:

- A workflow recurs and benefits from a named entry point ("Review this PR", "Summarize this meeting").
- The instructions are long enough that asking users to type them is friction.

Don't use prompts for:

- The system prompt of an agent. That belongs in the host.
- Tool selection logic. The model decides which tool to call; prompts can't override that.

Prompts are the least-used MCP primitive and will not be available in every client. Don't depend on them for core functionality.

## Pagination and large outputs

Tool outputs land in the model's context. A 500KB JSON response is a bad day for everyone.

Patterns:

- **Pagination.** Tools that can return many results take `cursor` and `limit` parameters and return a `next_cursor`. The model can request more if needed.
- **Summarization at the boundary.** A tool that fetches a 1000-line file might return the first/last 100 lines plus a summary, with a `read_range(file, start, end)` tool to fetch specific ranges.
- **Resource handles.** Return a URI/handle and let the model fetch ranges from a resource. Keeps the tool result compact.
- **Truncation with notice.** When you have to truncate, say so explicitly: `"... (output truncated; 847 more rows. Use limit/cursor to paginate.)"` Silent truncation produces silently wrong agent behavior.

A useful default: cap any tool result at a fixed token budget (4-8K tokens is typical) and have a strategy for what happens past that cap. "Whatever the underlying API returns" is not a strategy.

## Authentication

MCP servers are increasingly accessed by hosted LLM clients on behalf of users. Auth has to fit that model.

For local servers (stdio transport): inherit the user's credentials from the environment. The user runs the host; the host runs the server; the server has whatever access the user does. Simplest but only works locally.

For remote servers (HTTP/SSE transport): use OAuth. MCP supports OAuth 2.1 with discovery. Each user authenticates once; the host stores tokens; the server validates them per request. This is the right pattern for any multi-user service.

Avoid: API keys passed as tool parameters, hardcoded credentials in server config, "we'll add auth later." Adding auth later means redesigning the surface, because some tools become per-user that weren't.

For internal/single-tenant servers: a static bearer token from a config secret is acceptable. Document it clearly so it's never confused with an end-user auth mechanism.

## Transport

MCP supports stdio (process-based) and HTTP-based transports. Choose based on deployment:

- **stdio:** local server, host launches the process, simplest possible deployment. The right choice for tools that need access to the user's local machine — filesystem, local databases, user's editor state.
- **HTTP/SSE:** remote server, hosted, multi-user. The right choice for SaaS-style integrations where the server is centrally operated.

Don't expose a stdio server over HTTP without a proper auth and isolation layer. The stdio model assumes the user owns the process; HTTP assumes adversarial requests. The threat models are different.

## Idempotency and safety

Tools that have side effects deserve extra design attention.

- **Idempotency keys.** For tools that create or modify, accept an optional `idempotency_key` parameter. If the same key is reused, return the prior result rather than re-applying. Lets the model retry safely.
- **Two-phase commits for destructive actions.** Splitting `delete_record` into `prepare_delete` (returns a token + summary) and `confirm_delete(token)` lets the host display a confirmation UI between phases. Worth it for anything irrecoverable.
- **Dry-run modes.** A `dry_run: bool` parameter that returns what would happen without executing is an excellent debugging aid for both the model and the developer.
- **Scope limiting.** A tool that can edit any file is a tool that can edit `/etc/passwd`. Constrain the scope at the server level (e.g., "this server can only access files under the configured project root") and document the constraint.

## Security

Exposing capabilities to an LLM agent is exposing them to anyone whose content reaches that agent. This is the prompt injection threat (see `prompt-injection-defense`). Server-side defenses:

- **Principle of least privilege.** Each tool should do exactly what it says, with the minimum scope. A "read file" tool should not also be able to write. A "send email" tool should be scoped to a specific from-address, not given full mailbox access.
- **No admin tools without strong reason.** A tool like `execute_arbitrary_sql` or `run_shell_command` is a wide-open back door. Sometimes that's what you want (e.g., a coding agent on a sandbox). Often it isn't (e.g., a customer support assistant). Decide deliberately and document.
- **Input validation.** Validate parameters server-side. Don't trust the LLM not to send a `path: "../../../etc/passwd"`. The framework's schema validation is your first line; logical validation (does this path resolve inside the allowed root?) is your second.
- **Output sanitization.** When tool output will be rendered in a host UI, treat it as untrusted. A tool that returns user-generated content can be a vector for indirect injection downstream. Strip or escape executable elements.
- **Logging and rate limiting.** Log every tool call. Rate-limit per user. An agent with a bug or a prompt injection can call your tool 1000 times in a minute; without rate limits, that's an outage.

## Versioning

Tool surfaces evolve. Plan for that.

- **Additive changes are safe.** Adding a tool, adding an optional parameter — old clients keep working.
- **Breaking changes are not.** Removing a tool, making a parameter required, changing semantics. Either version your server (`v1`, `v2` namespaces) or coordinate with clients before changing.
- **Deprecation.** Mark old tools as deprecated in their description ("DEPRECATED: use `new_tool_name` instead"). The model will follow the guidance; this lets you migrate users gracefully.

For internal servers controlled with the clients, breaking changes are tolerable. For public/multi-tenant servers, treat the surface as a public API.

## Testing

Test the server like an API:

- **Unit tests** for each tool's logic.
- **Schema tests** verifying input validation rejects bad inputs and accepts good ones.
- **Integration tests** running the server as a subprocess and exercising it via the MCP protocol.
- **Agent-level evals.** Spin up a real LLM client against the server and verify it can complete representative tasks. The schema and descriptions you wrote work or they don't; the only way to know is to test.

For agent-level evals, see `llm-evaluation`. The pattern: a curated set of tasks, each with a success criterion. Run a host with the server; measure pass rate, tool calls per task, error recovery rate. Re-run on every server change.

## Observability

For each tool call, log:

- Tool name, parameters (with secrets redacted), caller identity.
- Result status (success, error class), latency, output size.
- Correlation ID linking back to the agent session.

For each session, log:

- Total calls, total cost (if metered), total latency.
- Error rate, pattern of failures.

A dashboard that shows "which tools are called most, which fail most, which are never called" is the most useful tool you can build. The "never called" column is especially useful — it tells you where your descriptions or schemas are failing to land.

## Anti-patterns

**The kitchen-sink server.** 50 tools because "the agent might need them." The model can't pick from 50 tools well; many will be unused; the descriptions are inevitably copy-pasted and bad. Trim to the essential surface.

**The undocumented schema.** Tool descriptions like "Performs the action" with no parameter docs. The model fails silently; nobody knows why.

**The error-as-text.** Errors thrown as exceptions that surface as "Internal Server Error" to the model. No recovery information, no class signal. The model retries the same call forever.

**The auth-as-parameter.** `api_key: string` as a tool parameter. The model has no business handling secrets, the host has no business passing them through, and they end up in logs.

**The unbounded result.** A `list_all` tool that returns 50,000 records on a busy day. Blows the context window, costs a fortune, the model never reads past the first page anyway.

**The hidden side effect.** A tool named `get_user` that, on the third call, decrements a quota counter. Surprises break agent behavior. Side effects belong in tool names and descriptions.

**The duplicate primitive.** A "wiki page" exposed as both a tool (`get_wiki_page(slug)`) and a resource (`wiki://team/...`). Now the model has to pick one and you've doubled your maintenance.

## Reference checklist

A production-ready MCP server has:

- A focused, well-named tool surface (typically 5-20 tools, not 50+).
- A description for every tool covering what/when/when-not/examples/errors.
- Full JSON Schema input definitions with descriptions, enums, and constraints.
- Structured output schemas where outputs are structured.
- Errors that are recoverable: classified, explained, with recovery guidance.
- Auth fit for deployment model (OAuth for remote, env-inheritance for local).
- Pagination/truncation strategy for large outputs.
- Rate limiting and per-call logging.
- Schema and integration tests, plus agent-level evals.
- A versioning policy.

## Related skills

- `agent-design` for the agent-side patterns your server is consumed by
- `prompt-injection-defense` for the threat model around exposing tools to agents
- `llm-evaluation` for measuring whether your server actually works in agent context
- `human-in-the-loop-workflows` for confirmation patterns on dangerous tools
