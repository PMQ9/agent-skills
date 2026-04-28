---
name: llm-application-engineering
description: Engineering practices for building production LLM applications — model selection, structured outputs, streaming, prompt caching, retry logic, cost and latency control, observability, and the boring infrastructure that determines whether an LLM feature ships or stays a demo. Use this skill whenever the task involves calling an LLM API from application code, designing the architecture of an LLM-powered feature, debugging flaky or expensive LLM calls, hardening a prototype for production, choosing between models or providers, or any work where someone says "we have a prompt that works, now we need to ship it." Trigger even when the user does not explicitly say "production" — most LLM code becomes production code, and the practices here apply from day one.
---

# LLM Application Engineering

A demo prompt and a production LLM application differ by an order of magnitude in code volume. The prompt is maybe 5% of what ships. The other 95% is everything around the call: structured outputs, retries, caching, fallbacks, telemetry, cost controls, evals, and the slow accumulation of glue that turns a fragile string-in-string-out function into a reliable component. This skill is about that 95%.

## The mental model

Treat every LLM call as a remote procedure call to a non-deterministic, occasionally-faulty, billed-by-the-token, sometimes-rate-limited service that returns text. Each property in that sentence demands engineering response:

- *Remote* → timeouts, retries, circuit breakers, fallbacks
- *Non-deterministic* → evals, golden tests, temperature control, structured outputs
- *Occasionally-faulty* → schema validation, refusal handling, output sanitization
- *Billed by the token* → caching, context trimming, model tiering, batch APIs
- *Rate-limited* → backoff, queueing, quota planning, multi-region/multi-key
- *Returns text* → parse defensively, never trust the shape

If your code does not have a story for each line above, it is not production-ready, regardless of how good the prompt is.

## Choosing a model

The cheapest model that meets quality bar wins. Always start with the smallest model in a family and only move up when an eval proves it is needed.

A working decision procedure:

1. Write the eval first. (See the `llm-evaluation` skill.) Without an eval, "quality" is whatever the developer remembers from yesterday.
2. Run the smallest model. If it passes, ship it. If it fails, look at *why* — is it a reasoning failure, a knowledge failure, or a formatting failure?
3. Fix formatting failures with structured outputs and few-shot examples, not a bigger model.
4. Fix knowledge failures with retrieval, not a bigger model.
5. Move to a larger model only when reasoning is the actual bottleneck.

Mixing model tiers within one feature is normal and good. A common pattern: small model classifies/routes, large model handles the hard subset, smallest model formats the final output. Each call gets the model it deserves.

Reasoning models (those that think before answering) trade latency and cost for quality on multi-step problems. They are not a free upgrade — for short, well-defined tasks they are slower and more expensive without being better. Reach for them when the task involves planning, math, or multi-constraint synthesis.

## Structured outputs

Free-text outputs are a debugging tax you pay forever. Use structured outputs (JSON schema, function calling, tool use) whenever the output will be programmatically consumed. Three things this gets you:

1. **Parse safety.** No more regex over English prose, no more "the model started its answer with 'Sure!' today."
2. **Field-level evaluation.** You can write assertions like `output.confidence > 0.7 implies output.action != "skip"` instead of grading paragraphs.
3. **Refusal handling.** A schema with a `refusal` or `cannot_answer` field gives the model a structured way to decline, instead of free-text refusals you have to detect.

Schema design rules:

- Make fields the model has to fill explicit. `{"answer": "...", "citations": [...]}` beats `{"response": "..."}` because the second one lets the model forget citations.
- Order fields in the order you want the model to think. Put `reasoning` or `analysis` before `answer` if you want chain-of-thought; put it after if you want the answer to drive the explanation. Models attend to the order.
- Use enums liberally. `"action": "approve" | "reject" | "escalate"` is enforceable; `"action": "string"` is a coin flip.
- Avoid deeply nested optional structures. Flat schemas with required fields fail loudly when the model gets confused, which is what you want.

When the provider does not enforce JSON natively, validate with a schema library (Pydantic, Zod, JSON Schema) and treat validation failure as a retryable error with the validation message fed back into the next attempt.

## Prompt caching

Prompt caching reuses the KV-cache for repeated prefixes across calls. When supported by the provider, it cuts cost (often by 90% on the cached portion) and latency (often by 50%+) for any prompt with a stable prefix.

Things that should be cacheable, in order of priority:

1. The system prompt
2. Tool/function schemas
3. Long context documents (RAG results that are stable across a conversation, large reference materials)
4. Few-shot examples
5. Conversation history up to the latest turn

Things that break caching: putting per-request data (user ID, timestamp, random ID) early in the prompt, regenerating few-shot examples per request, reordering tools.

Architect prompts as `[stable prefix][variable suffix]`. If you find yourself interpolating user data into the system prompt, move it to the user message instead.

## Streaming

Stream when a human is waiting for the output. Do not stream when a program is consuming it — you gain nothing and complicate the code.

Streaming complicates three things:

- **Error handling.** Errors can arrive mid-stream after you've already shown 80% of the answer. Plan for this in the UI (e.g., a "regenerate" affordance) and in the backend (don't commit partial outputs to the database until the stream finishes cleanly).
- **Tool use / structured outputs.** With JSON mode, partial JSON is invalid JSON. Either parse incrementally with a streaming JSON parser, or stream only the human-visible parts and emit structured fields at the end.
- **Cost accounting.** Token counts arrive at the end of the stream. Plan your billing/quota code accordingly.

For agent-style applications, stream the *reasoning* but not the *tool calls*. The user wants to see thought; they don't want to watch the model serialize a function call character by character.

## Retries, timeouts, and fallbacks

The right retry policy depends on the error class. Treat them as distinct:

- **Transient (5xx, network, timeout):** Retry with exponential backoff and jitter. 3 retries is the usual ceiling — beyond that, fail loudly.
- **Rate limit (429):** Honor the `Retry-After` header if present. Otherwise backoff aggressively. Consider a queue rather than busy-retrying.
- **Schema validation failure:** Retry once with the validation error appended to the prompt. Do not retry indefinitely — some failures are systematic.
- **Content filter / safety refusal:** Do not blindly retry. Either rephrase, route to a different model, or escalate. Retrying the same call invites the same refusal and burns money.
- **4xx other than 429 (bad request, auth):** Do not retry. These are bugs.

Set timeouts. The default of "wait forever" will eventually take down your service. A sensible default is 60s for normal calls, longer for reasoning models or very long contexts. Always set a per-call timeout, not just a session timeout.

Fallbacks: when a provider is down or rate-limited, route to a backup. The simplest version is "if Anthropic is unavailable, use OpenAI" with a normalized client interface. The harder version (different prompt formats, slightly different behavior) is real engineering work — budget for it before you need it.

## Cost control

LLM costs scale with usage in ways that surprise teams. A few defenses:

- **Per-user/per-tenant budgets.** Hard cap spend per actor at the application layer, not just at the provider account level. Without this, one runaway script or abusive user can drain a month's budget overnight.
- **Token budgets per call.** Set `max_tokens` deliberately. The model will fill the space if you let it; "give me a summary" with 4096 max_tokens will produce a 4096-token summary.
- **Context trimming.** Truncate or summarize conversation history before it explodes. A 10-turn chat at 2000 tokens/turn becomes a 20k-token call by turn 10. Strategies: sliding window of last N turns, summarize older turns, drop tool outputs older than M turns.
- **Batch APIs.** Many providers offer 50% discounts for batch (async) processing. Use them for any non-interactive workload — overnight reports, bulk classification, dataset labeling.
- **Cache hit instrumentation.** Log cache hit rates. A regression in cache hit rate from 80% to 30% will double your bill silently.

A useful rule: every LLM call should have an associated *cost ceiling* set by the caller, not the provider's account-level limit. The application is responsible for not running away.

## Latency budgets

Set a latency budget per user-facing interaction. Common budgets:

- Synchronous chat: first token under 1s, completion under 10s
- Search/retrieval augmentation: under 500ms added latency for RAG
- Background agent step: under 30s, with progress visible to the user

Strategies for hitting them:

- Smaller model. Almost always the biggest lever.
- Streaming (improves perceived latency even when total time is unchanged).
- Parallel tool calls instead of sequential.
- Prompt caching.
- Pre-computing/pre-fetching obvious next steps.
- Speculative execution (start a likely tool call before the model asks for it; cancel if it goes another way).

If you are over budget and out of tricks, the answer is usually to redesign the UX (async, batch, "we'll email you the result") rather than make the LLM faster.

## Observability

You cannot improve what you cannot see. Every LLM call should produce a trace with:

- Full prompt (system + user + tool messages), with sensitive fields redacted
- Full response, including reasoning/tool calls
- Model, temperature, max_tokens, other params
- Token counts (prompt, completion, cached, total)
- Latency (TTFT and total)
- Error / refusal status
- A correlation ID linking to the user request, agent loop, etc.

Sample heavily in production. Even if you cannot store every trace, store every *failure*, every *refusal*, and a sampled fraction of successes. Without traces, debugging an LLM regression is archaeology.

Tools that do this well: Langfuse, Helicone, Braintrust, Honeycomb with OTEL spans, Weights & Biases. Roll your own only if you have very specific needs — the data model is harder than it looks (variable-length messages, tool calls, multi-modal content).

## Determinism and reproducibility

LLMs are non-deterministic even at temperature 0. (Floating-point nondeterminism in batched inference, model version drift, sampling on tied logits.) Plan for this:

- Pin model versions explicitly. Never use `claude-opus-latest` or equivalent in production — use a dated identifier so you control upgrades.
- Record the model version in every trace.
- When debugging a failure, run the exact prompt 5+ times. Intermittent failures are the norm, not the exception.
- Eval suites should include variance tests (run each case N times) before declaring a regression.

## Common anti-patterns

These show up constantly. Recognize them by name and refuse them:

**The God Prompt.** A 3000-line system prompt accumulated over months, full of "IMPORTANT:" and "DO NOT FORGET:" clauses for every bug ever found. Symptoms: nobody on the team knows what every line is for, removing anything is terrifying, the model still ignores it sometimes. Treatment: split into composable subprompts, write evals for each instruction, delete what evals show is no-op.

**The Naked API Call.** `result = client.messages.create(...)` with no retry, no timeout, no validation, no logging. Works in dev, fails the first time the network hiccups in prod.

**The Format Wish.** "Please return your answer as JSON" in the prompt, with no schema enforcement and no validation. Works 95% of the time, breaks at exactly the wrong moment.

**The Infinite Context.** Conversation history grows unbounded. Latency and cost grow with it. Eventually hits context window limits and the app silently breaks.

**The Untested Refactor.** Prompt is changed because it "should be cleaner," with no eval run before/after. Quality regresses; nobody notices for two weeks.

**The Single-Model Codebase.** Every call uses the flagship model "to be safe." Cost is 10x what it needs to be. Latency is 3x. Easily caught by a model-tier audit.

**The Mystery Refusal.** Model refuses; code returns a generic error to the user. No metric, no log, no retry strategy. Nobody knows refusals are happening at all.

## A reference structure for an LLM call

```python
# Illustrative — `Prompt`, `start_trace`, and `retry_delay` are project-defined.
# Anthropic SDK shown; OpenAI/Bedrock have analogous shapes.
import random
import asyncio
from anthropic import AsyncAnthropic, APIStatusError, APITimeoutError, RateLimitError
from pydantic import ValidationError

client = AsyncAnthropic()

def _extract_text(response) -> str:
    # response.content is a list of content blocks (TextBlock | ToolUseBlock | ...).
    # Concatenate text blocks; ignore tool_use here (handle separately if you allow tools).
    return "".join(b.text for b in response.content if b.type == "text")

def _backoff(attempt: int, retry_after: float | None = None, cap: float = 30.0) -> float:
    if retry_after is not None:  # honor server hint (Anthropic and OpenAI both surface this)
        return min(cap, retry_after)
    base = min(cap, 0.5 * (2 ** attempt))
    return random.uniform(0, base)  # full jitter

async def call_llm(
    prompt: "Prompt",
    *,
    schema: type[T],
    model: str,
    max_tokens: int,
    timeout_s: float = 60.0,
    correlation_id: str,
) -> T:
    trace = start_trace(correlation_id, prompt, model)
    try:
        for attempt in range(3):
            try:
                async with asyncio.timeout(timeout_s):
                    response = await client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        system=prompt.system,
                        messages=prompt.messages,
                        tools=prompt.tools or [],
                    )
                trace.record_response(response)
                parsed = schema.model_validate_json(_extract_text(response))
                trace.record_success(parsed)
                return parsed
            except ValidationError as e:
                if attempt == 2:
                    raise
                prompt = prompt.with_validation_feedback(e)  # project helper
            except RateLimitError as e:
                # SDK exposes response headers including `retry-after`
                retry_after = float(e.response.headers.get("retry-after")) if e.response else None
                await asyncio.sleep(_backoff(attempt, retry_after))
            except (APITimeoutError, APIStatusError, asyncio.TimeoutError):
                if attempt == 2:
                    raise
                await asyncio.sleep(_backoff(attempt))
    finally:
        trace.finish()
```

This is not the only shape, but every production wrapper has these elements: structured input, content-block-aware extraction (Anthropic returns a list of content blocks, not a JSON string), schema-validated output, bounded retries with the right policy per error class (honoring `retry-after` for rate limits, full jitter elsewhere), a timeout, a trace. A new LLM feature should reuse one of these wrappers, not call the SDK directly.

For structured outputs natively, prefer the provider's first-class mechanism (Anthropic tool use with a JSON schema and `tool_choice`; OpenAI `response_format={"type": "json_schema", "strict": true}`) instead of free-text + post-hoc validation when the call is purely for data extraction.

## What to read next

For specific subdomains, see the related skills:

- `agent-design` for multi-step LLM systems and tool use loops
- `rag-architecture` for retrieval-augmented patterns
- `llm-evaluation` for the eval discipline this whole skill assumes
- `prompt-injection-defense` for adversarial inputs
- `human-in-the-loop-workflows` for when not to automate
