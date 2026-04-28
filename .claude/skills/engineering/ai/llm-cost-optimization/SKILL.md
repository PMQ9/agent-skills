---
name: llm-cost-optimization
description: Use this skill for reducing the token cost and latency of LLM-powered systems — model selection (Opus/Sonnet/Haiku, GPT-5/4o/4-mini, Gemini Pro/Flash, open-source), prompt caching (Anthropic, OpenAI, Gemini implementations), context compression, output length control, batch APIs, model routing/cascades, semantic caching, RAG vs fine-tuning trade-offs, structured outputs to cut retries, streaming, parallel tool calls, distillation, the "smaller model after a big model proves the prompt works" pattern, and reading token bills to understand where costs are coming from. Trigger when a user mentions LLM costs, "the bill is too high," budget caps, latency reduction, "this is too expensive to run," "we need to use a cheaper model," prompt caching, batching, or any time a system is being moved from prototype (where cost was acceptable) to production (where it isn't).
---

# LLM Cost Optimization

Two categories of LLM cost problem dominate. The first: **the system works, but it's too expensive.** The bill is real, the value is real, the ratio is wrong. The second: **the system is fine on cost in dev, will be ruinous at scale.** Both need the same toolkit, but the order of operations differs. This skill is the toolkit, in rough priority order.

The single most important orientation: **measure before optimizing.** Most teams, when asked where their LLM cost goes, are wrong about it. A ten-minute exercise — pull last week's tokens grouped by feature, by model, by prompt template — usually reveals that 80% of the cost is in 1-2 places, and the optimization plan writes itself. Without that exercise, you'll spend a week tuning the part that doesn't matter.

## How LLM costs actually work

A few facts that govern everything below:

1. **Output tokens cost more than input tokens** — typically 3-5x more, depending on model. Anthropic Sonnet 4.6 is roughly $3/M in vs $15/M out; GPT-5 family and Gemini families are in similar ratios. Cutting an unnecessarily verbose response cuts more cost than cutting input.
2. **Cached input tokens cost much less than fresh input.** Anthropic's prompt caching is ~10% of base input cost on cache hit; OpenAI's automatic caching is 50%; Gemini's caching is similar. For high-volume systems with stable prefixes, this is the highest-leverage optimization most teams miss.
3. **Batch APIs cost ~50% of synchronous.** If the work doesn't need to be real-time, batch it.
4. **Smaller models cost an order of magnitude less.** Haiku is ~12x cheaper than Sonnet on input, ~20x cheaper on output. GPT-5-mini vs full GPT-5 is similar. For a non-trivial fraction of calls in most systems, the small model is good enough.
5. **Tokens ≠ characters.** ~4 characters per token in English on average; code, JSON, and non-Latin scripts vary significantly. Use the provider's tokenizer for real counts; rough estimates lie.

## Step 1: Measure

Before optimizing, instrument:

- **Per-feature token counts** — input/output split, cache hit/miss split — tagged at the call site.
- **Per-model spend** — Anthropic and OpenAI both surface this in their dashboards; you also want it in your own metrics for cross-checking.
- **Token distribution per request** — p50, p95, p99. The p99 of a long-context system is often where the cost lives.
- **Cache hit rate** — if it's 0%, you're not using caching; if it's 99%, you might be over-caching things you'll never reuse.

Tools: Langfuse, LangSmith, Helicone, Datadog LLM Observability, OpenTelemetry GenAI semconv → your existing observability stack. Pick one early. The "I'll just look at the dashboard" approach loses signal; you can't slice by feature or filter by user cohort.

A useful exercise: sort last week's spend by `(feature, prompt_template)`, descending. The top 3 lines almost always account for > 50% of cost. Optimize those.

## Step 2: Pick the right model per call

Most production LLM systems use one model for everything. This is almost always wrong. Different calls in the same system have wildly different difficulty:

| Call type | Model that's usually enough |
|---|---|
| Classification (intent, sentiment, routing) | Haiku / GPT-5-mini / Gemini Flash |
| Extraction with a clear schema | Haiku / GPT-5-mini / Gemini Flash |
| Summarization of structured input | Haiku / Sonnet (judgment call on length) |
| Fluent reply generation in a conversation | Sonnet / GPT-5 / Gemini Pro |
| Multi-step reasoning, tool-use planning | Sonnet / GPT-5 |
| Hard reasoning (math proofs, novel architecture) | Opus / GPT-5 thinking / Gemini Pro thinking |
| Code generation (non-trivial) | Sonnet / GPT-5 |
| Code editing (small, well-defined) | Haiku / Sonnet |

The pattern: **start the build on a strong model** (you don't want to debug a prompt fighting model capability). Once the prompt works, **try the next model down**. Run an eval. If it still passes, ship the smaller model. Repeat until the eval breaks; back up one step.

This is the single highest-leverage optimization for most systems, and the most overlooked. Teams ship Sonnet/GPT-5 for everything because that's what they prototyped on, and never test whether Haiku would do.

The corollary: **the model lineup changes.** Haiku 4.5 is dramatically more capable than Haiku 3.5. The "we tried the small model a year ago, it didn't work" data is stale by now. Re-test on a quarterly cadence; the cost line keeps moving down.

### Model routing / cascades

When difficulty varies request-to-request, route:

```
                    ┌── Easy:   Haiku
Classifier ─────────┼── Medium: Sonnet
                    └── Hard:   Opus
```

Two ways to implement:

- **Pre-classifier**: a cheap model (or rules) classifies difficulty and picks the executor. Adds a call.
- **Cascade with verification**: try the small model first; if its output fails a check (validation, low confidence, schema mismatch), retry on the bigger one. Pays small-model cost on the easy 80%, both costs on the hard 20%.

Cascades work well when small-model failure is detectable. For free-form generation, "is this answer good?" is hard to verify cheaply, and cascades save less. For structured tasks (extraction, classification), schema validation is a free verifier and cascades work great.

A common pattern in production: tool-call routing. A small model decides "should I use a tool?" and which one. The tool itself might invoke a bigger model. Most queries never need the bigger model.

## Step 3: Use prompt caching

The single most under-applied optimization. If you are sending the same system prompt or context to the model repeatedly, you should be caching it.

### Anthropic (explicit cache breakpoints)

```python
response = client.messages.create(
    model="claude-sonnet-4-7",
    system=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT,           # large stable prefix
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": user_query}],
)
```

- Up to 4 cache breakpoints per request.
- Cache lifetime: 5 minutes (default) or 1 hour (with extended TTL).
- First call writes the cache (~25% premium on input); subsequent calls within TTL hit the cache (~10% of base input cost).
- Cache key includes everything **before** the breakpoint exactly; one byte different and you miss.

### OpenAI (automatic)

OpenAI caches automatically on prompts > 1024 tokens. You don't ask for it; it just happens. Hit gives ~50% off cached portion. The cache is per-organization, partitioned for privacy.

### Gemini (explicit `cachedContent`)

Create a cache once with `client.caches.create(...)`, get a cache name, reference it in subsequent calls.

### What to cache

Anything stable across many calls:

- System prompts (especially long ones).
- Few-shot examples.
- Tool definitions.
- Reference documents you're answering questions about (a manual, a codebase chunk, a legal contract).
- Conversation history in a long-running session — cache up to "before the latest user turn."

The pattern that wins: **stable prefix → variable suffix.** Put everything that doesn't change at the start. Put the only thing that changes (the user's specific request) at the end. This maximizes cacheable portion.

### Common caching mistakes

- **Cache miss because the prefix isn't byte-stable.** A timestamp injected into the system prompt, a user ID, a randomized example order — all kill the cache. Audit the prefix for variability.
- **Caching things that change every call.** No benefit, possibly a cost premium on the first write.
- **Not caching tools across an agent loop.** The same tool definitions go in every turn; cache them once.
- **Underestimating impact.** For an agent that does 10 turns over a 10K-token system prompt, caching turns ~100K input tokens into ~10K of cached + ~90K of cache-hit-priced. Real savings, with no quality change.

For long-running conversations (chatbots, agents), caching is the difference between affordable and not. For one-shot calls with unique prompts, it does nothing.

## Step 4: Control output length

Output tokens are 3-5x the price of input. Verbose responses are an outsized cost driver.

Tactics, in order:

1. **Tell the model how long.** "Reply in 1-2 sentences." "Maximum 100 words." "Return only the JSON, no preamble." Cheap, effective.
2. **Use `max_tokens` as a hard cap.** Set it to the longest reasonable response, not the model's default ceiling. Truncated outputs are sometimes a quality win — the model rambles less when constrained.
3. **Prompt for terse structure.** "Bullets, no prose explanation." "Just the answer."
4. **Stream and stop early when possible.** If the consumer of the response can decide partway through that it has what it needs (e.g., parsed the first JSON object), abort the stream.
5. **Use `stop_sequences`** to halt generation at known boundaries.
6. **Avoid extended/thinking modes when not needed.** Reasoning models (o-series, Claude with extended thinking, Gemini thinking) generate hidden reasoning tokens you pay for. Use them when the task benefits, not by default.

### Structured outputs cut retries

If you need JSON, use the structured output modes (Anthropic JSON mode / tool use, OpenAI Structured Outputs with strict schemas, Gemini structured output). They eliminate "model returned malformed JSON, retry" loops. A retry doubles the cost of that call.

Schema-validated outputs have another benefit: **shorter, more deterministic outputs.** A free-form "describe this customer's complaint" may run 300 tokens; a schema with `{summary: string, severity: enum, ...}` runs 50 and is more useful.

## Step 5: Manage context size

Input cost scales linearly with context. RAG systems that stuff 50 chunks "to be safe" pay for that safety on every query.

The levers:

### Retrieve less, retrieve better

- **Top-k tuning** — start at k=5, only go higher if eval shows it helps. Most RAG systems perform fine at k=3-5 with good retrieval and lose nothing at k=20.
- **Reranking** — retrieve 50, rerank to keep the top 5. The rerank model is cheap; the LLM call on 5 reranked chunks beats the LLM call on 50 raw ones, both in quality and cost.
- **Hybrid search** (vector + keyword) — improves precision, lets you reduce k.

The `rag-architecture` skill covers this in depth.

### Compress conversation history

For multi-turn chats, the context grows linearly with turn count. Three patterns:

- **Sliding window** — keep last N turns. Loses old context.
- **Summarize old turns** — every K turns, replace the oldest M turns with a summary. Cheap if summaries are generated by Haiku.
- **Selective retention** — keep only the user-system pairs that scored as relevant by a small classifier. More work; rarely worth it over summarization.

### Trim tool results

Tool outputs can balloon: a search returning 20 hits, each with a long snippet. Truncate to what matters before passing back to the model.

```python
# Bad: pass the whole tool output
search_result = search(query)  # ~5K tokens
return {"role": "user", "content": str(search_result)}

# Good: trim to the parts the model needs
return {
    "role": "user",
    "content": json.dumps([
        {"title": h.title, "snippet": h.snippet[:200], "url": h.url}
        for h in search_result.hits[:10]
    ])
}
```

### Strip system prompts you don't need

It's common to inherit a 4000-token system prompt that started as one paragraph and grew over time. Audit it. Cut sections that are redundant, never triggered, or describe behavior the current model already does. Then run evals to confirm nothing broke.

## Step 6: Use the batch API for non-realtime work

If your work doesn't need to be synchronous — overnight enrichment, report generation, bulk classification, eval runs — use the batch API. ~50% off, with a 24-hour completion SLA.

Anthropic's Message Batches API, OpenAI's Batch API, Gemini batch mode all work the same way: submit a JSONL file of requests, poll for completion, download results.

Common candidates:

- Embedding/labeling a corpus.
- Generating eval results.
- Periodic re-summarization of long conversations.
- Email replies that don't need instant response.
- Anything triggered by a queue without strong latency requirements.

## Step 7: Cache at the application layer

LLM-provider prompt caching is one tier. Application-level caching is another.

### Exact-match cache

Same input → same output. A simple key-value store keyed on a hash of the request. Works for:

- Idempotent enrichment ("classify this product description").
- Highly repetitive queries ("summarize this article" — when the same article gets summarized many times).
- FAQ-shaped systems where many users ask the same question.

Beware staleness: cache invalidation is the hard part. Set a TTL appropriate to how often the underlying data or model changes.

### Semantic cache

Match queries that are *similar* to ones you've answered. Embed the new query, compare to embeddings of past queries, return cached answer if similarity > threshold.

Useful, but a footgun: "What is X?" and "What is not X?" are semantically close but want different answers. Calibrate carefully; require high similarity thresholds; bias toward exact-match where the value is small.

Tools: GPTCache, Redis Vector Search for the cache index, or roll-your-own with pgvector. Most production systems are better off with exact-match + good UX (let users edit/refine) than with semantic caching.

## Step 8: Reduce calls

The cheapest LLM call is the one you don't make.

### Combine sequential calls into one

If your pipeline calls the model twice ("first classify, then respond") and the second call has all the context needed for the first, just make one call. Tell the model to do both, return both as structured output.

### Skip the LLM when rules suffice

A non-trivial fraction of calls in many systems are doing things rules can do:

- "Is this a question or a command?" → look for `?`, count question words.
- "Is this a customer-support topic we handle?" → keyword match.
- "Should we use the search tool?" → if the query mentions specific entities, yes.

A short rule layer in front of the LLM filters out cases that don't need it. This is also why router/classifier patterns work: the cheap classifier handles 80% of decisions; the LLM gets the actual hard ones.

### Don't re-call to fix the response

If you need to validate or clean up an LLM output, do it deterministically (regex, schema validation, small parsing logic). Don't make a second LLM call to "fix the JSON." Use structured outputs that can't produce broken JSON in the first place.

### Parallel tool calls when possible

If an agent needs three pieces of info, the model can request all three tool calls in one turn (Anthropic, OpenAI, Gemini all support parallel tool calls). Run them concurrently, return all results in one user message. One round trip instead of three.

## Step 9: Distillation and fine-tuning

When all the prompt engineering is done and a smaller model still doesn't pass evals, **distillation** is the next lever. Generate training data from the big model's outputs, fine-tune a smaller model on that data, ship the small model.

Works best when:

- The task is narrow (single domain, structured output).
- You have hundreds-to-thousands of examples (or can generate them).
- The base small model is reasonably close already.

Returns are huge when it works: 10-20x cost reduction with comparable quality on the in-domain task.

Beware:

- The distilled model is **only good at what you trained it on.** Out-of-distribution inputs perform worse than the original prompt-on-big-model would have.
- Maintenance — the underlying foundation model improves; your distilled model doesn't until you re-train.
- Vendor lock — fine-tuned models are vendor-specific. The distilled OpenAI model doesn't run on Anthropic.

Open-source small models (Llama 3.x/4, Qwen, Mistral, Gemma) are strong distillation targets and run on your own infrastructure — with corresponding ops cost. For most teams, distillation onto a hosted small model (GPT-5-mini fine-tune, Haiku fine-tune via Bedrock when available) is the practical option.

For most systems, **don't reach for fine-tuning until you've exhausted prompt engineering.** Prompt engineering is reversible and cheap; fine-tuning is committed and expensive to maintain. Most "we need to fine-tune" instincts go away after a session of serious prompt and example work.

## Step 10: Latency optimization (related but different)

Latency and cost optimizations overlap but aren't identical.

For latency:

- **Streaming** doesn't change cost but makes apparent latency lower (TTFT, time-to-first-token).
- **Smaller model** is faster (almost always).
- **Shorter output** is faster.
- **Parallel tool calls** reduce wall-clock for agent loops.
- **Caching** is a latency win as well as cost (cached prefixes process much faster, ~70-90% reduction in TTFT for cached portions).
- **Speculative decoding / cascades** — fast model produces a draft, slow model verifies. Some providers offer this implicitly; you can build it explicitly.
- **Geographic colocation** — if you're calling from us-east-1, use the closest model endpoint. Cross-region adds 50-200ms.
- **Pre-warming** — keep a connection pool open; cold connect handshakes add latency.

The latency you see ≈ TTFT + output_tokens / tokens_per_second. Both terms have separate levers.

## Reading the bill

Every couple of weeks, an engineer should sit down with the dashboard and answer:

1. **What feature/endpoint costs the most?** (Sometimes surprising.)
2. **What's the cache hit rate?** (Often 0% for teams who haven't deliberately set it up.)
3. **What's the input/output ratio per call?** (Outputs longer than expected = prompt-side issue.)
4. **What's the spread of token counts?** (p99 / p50 ratio reveals long-tail cost.)
5. **What's the per-user cost?** (A few power users can dominate the bill.)
6. **What model is being used where?** (Often Sonnet is doing things Haiku could do.)

Each of those questions points at a specific lever. The first time you do this exercise, the answers usually direct a 30-50% cost reduction in the next sprint, before you touch any model code.

## Cost-engineering by system type

Common production systems, and where their costs typically concentrate:

### Chatbot / customer support

- Big spend driver: long conversation contexts, repeat tool definitions.
- Levers: prompt cache the system prompt + tools; summarize old turns; route easy queries to a cheap model first.

### RAG over docs

- Big spend driver: retrieved context per query, especially with high k.
- Levers: rerank to reduce k; cache the system prompt; route metadata-only questions to a cheap model that doesn't see retrieved content.

### Agentic system (research, coding, ops)

- Big spend driver: agent loops with growing context, many turns.
- Levers: cache system prompt + tools; subagents on cheap models with summaries returned; cap iterations; use Haiku for "navigation" steps and Sonnet for "synthesis" steps.

### Bulk enrichment / classification

- Big spend driver: high volume of similar calls.
- Levers: batch API; smallest model that passes eval; structured outputs to eliminate retries; consider distillation if volume is sustained.

### Document/code generation

- Big spend driver: long output tokens.
- Levers: explicit length constraints; structured outputs; smaller model on the parts that don't need creativity; verify-and-cascade pattern.

## Common anti-patterns

- **No measurement, "let's optimize."** Wrong things get optimized. Measure first.
- **One model for everything.** The biggest model in the lineup, applied uniformly. Almost always overspending.
- **Cached nothing.** No prompt caching configured. Easy 50%+ savings missed.
- **Cache misses you didn't notice.** Caching configured, but the prefix has a timestamp or user ID baked in. Cache hit rate is 0%; you don't know.
- **Verbose by default.** Outputs ramble because nothing tells the model not to.
- **Structured outputs not used; retries when JSON breaks.** Effectively double the cost of those calls.
- **Synchronous API for batch work.** Paying 2x for latency you don't need.
- **Fine-tuning as the first optimization.** Premature commitment. Prompt-engineer first.
- **Reasoning/thinking modes left on by default.** Reasoning tokens are expensive; they earn their cost on hard problems, not on classification.
- **One giant context per call** to "give the model everything." The model doesn't need everything; you're paying for the noise.
- **Embedding the same context in every conversation turn** instead of relying on the cached prefix.
- **Different versions of the same prompt** drifting across the codebase. Each call has different cache keys, no cache benefit. Centralize prompt templates.
- **Token counts grow over time** because nothing trims old context, and nobody re-evaluates.
- **No per-feature cost attribution.** "The bill is high" with no idea where. Tag your calls.
- **Caching abuse** — caching things that change every call, paying the write premium for nothing. Profile first.
- **Skipping evals after switching models.** Cheaper but worse-quality is rarely the right trade. Always eval the swap.

## A reasonable cost-optimization sprint

If you're handed a "this is too expensive, fix it" problem and have a week:

1. **Day 1**: instrument cost per feature/template/model. Find the top 3 cost lines.
2. **Day 2**: for the top 3, measure cache hit rate, p50/p99 input/output, model being used.
3. **Day 3**: configure prompt caching on the largest stable prefixes. Measure impact.
4. **Day 4**: try the next-smaller model on the top cost line. Run evals.
5. **Day 5**: tighten output length. Add structured outputs where retries are happening.
6. **Day 6**: route easy traffic away from the biggest model.
7. **Day 7**: measure new bill, write up changes, set up an alerting threshold so this doesn't drift back.

A typical result: 40-70% cost reduction with no quality loss, no fine-tuning, no architecture rewrite. The ones who get to "we need to fine-tune" almost always haven't done these seven days yet.

## When cost is not the right framing

Sometimes the answer is: **the LLM call is providing $X of value and costing $Y; if X >> Y, don't optimize.** A research agent that costs $0.50 per query and saves an analyst 30 minutes is correctly priced. Spending engineering effort to make it cost $0.05 is a poor trade if the engineering time costs more than the savings will recover within a reasonable horizon.

Reach for cost optimization when:

- The system is at a scale where the bill is meaningful (not just tracking-toward-meaningful).
- The cost-to-value ratio is genuinely off.
- Cost is blocking adoption (free tier impossible, customer acquisition cost too high).

Otherwise, ship features and revisit cost when scale demands it. Premature cost-optimization is its own bug class — systems that are marginally cheaper but harder to reason about, harder to debug, and quality-degraded by an over-aggressive small model.
