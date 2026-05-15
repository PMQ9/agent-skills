---
name: local-llm-delegation
description: Use this skill when the user has a local Ollama server and the task is bulk, mechanical, easily-verifiable, or privacy-sensitive — anything where offloading to a 3B-8B local model would save Claude context and API tokens. Trigger on document processing at volume (OCR a PDF, transcribe audio, extract fields from many emails), mechanical code (CRUD scaffold, Pydantic models, 1:1 renames), bulk classification or routing ("which tickets are billing?"), embeddings for RAG/dedup, fast triage ("is this relevant?"), screenshot/UI parsing, and any time you're about to burn many tokens on work a small model could plausibly do. Trigger even when the user didn't say "Ollama" — if it's set up, often delegate without asking. Do NOT trigger for judgment-heavy reasoning, full-repo-context work, confident-wrong-is-expensive tasks, or one-shot questions you can just answer.
---

# Local LLM Delegation

You have a small fleet of local models running under Ollama on this machine.
The point of this skill is to make you *consciously decide* whether the task in
front of you should be done by you or handed off to one of them — and to give
you the exact commands and decision rules to do it well.

## The core idea

You — Claude, frontier model, expensive context — are a scarce resource for the
user. The local models are not. Anything that's bulk, mechanical, easily checked,
or just needs a competent intern is a candidate to delegate. The wins compound:
the user's context window stays clear, their API bill shrinks, latency on the
big stuff stays low, and privacy-sensitive content can stay on their machine.

The cost of delegating is real but cheap: you write one prompt, the local model
runs it, you read the output, and you either pass it through or verify a sample.
The cost of *not* delegating when you should is invisible — you just quietly
spent thousands of tokens on something a 3B model would have nailed.

Default toward delegating bulk work. Default toward doing judgment work
yourself.

## When to delegate (default: yes)

Hand off to a local model when the task is any of these:

- **Bulk and repetitive.** "Summarize each of these 40 emails," "extract sender
  + date + amount from each receipt," "classify each item as A/B/C." Per-item
  work over a list is the canonical local-model job. You frame it once; the
  small model grinds through it.
- **Mechanical code.** Boilerplate scaffolds, 1:1 renames, schema-to-class
  generation, syntax fixes that compile-or-don't, formatting a list of strings
  into a typed enum. The verifier is cheap (it parses or it doesn't, the test
  passes or it doesn't).
- **Easily verifiable.** Anything where the output has a schema, or matches a
  ground truth, or is a yes/no the user can spot-check at a glance. Local models
  are at their best when "is this wrong?" takes one second to answer.
- **Privacy-sensitive.** Patient notes, internal HR docs, anything the user
  would rather not send to a hosted API. The local model never leaves the
  machine.
- **Vision / audio.** OCR, screenshot parsing, chart reading, transcription.
  You don't natively process audio at all; vision is expensive when you do. A
  call to `qwen3vl` or `gemma3n` is often the right move just on cost grounds.
- **Pre-filtering big corpora.** Use `nomic-embed-text-v2-moe` to produce vectors,
  then narrow 10,000 docs down to the 50 worth your attention. Embeddings are
  almost free — use them freely.

## When NOT to delegate (do it yourself)

- **One-shot, in-context.** If the user asked you a question and you can answer
  it in this response, just answer. Don't manufacture a delegation step for
  something you'd finish in the time it takes to write a prompt.
- **Repo-aware, multi-file reasoning.** Work that depends on holding a lot of
  the codebase or conversation in mind. The local model doesn't have your
  context. (Note: `qwen3.6` with thinking is stronger here, but for genuine
  repo-level work, do it yourself.)
- **Confident-wrong is expensive.** Medical, legal, safety, money-moving,
  anything the user will act on without re-reading carefully. A frontier model
  saying "I'm not sure" is worth more than a 3B model saying "yes" with the
  same confidence as "no."
- **Judgment / taste / nuance.** Tone of voice, persuasive writing, tricky
  product decisions, code architecture. The small model produces plausible
  text; that's different from good.
- **The user explicitly asked for you.** "Claude, what do you think of X?"
  Don't punt to a local model. Answer it.

If you're on the line, a useful gut check: *could I sample 3 of the local
model's outputs and tell at a glance whether they're right?* If yes, delegate.
If no, do it yourself.

## Model selection

Pick the smallest model that can do the job. These are the models the user has
configured on this machine; see `references/recipes.md` for worked examples per
model.

| Model | Modality | Best for |
|---|---|---|
| **llama3.2:3b** / **phi4-mini:3.8b** | Text | Triage, routing, "is this relevant?", quick cleanup. Fastest things on the box. |
| **gemma3n:e4b** | Text + Image + Audio | Audio transcription, audio Q&A, light image captioning, low-RAM machines. The only one that hears. |
| **qwen3** | Text | General-purpose: summarize, draft, extract structured data, shape JSON / tool-call payloads. Reliable instruction follower. |
| **qwen3.6** | Text + tools + long context, optional thinking | Hard reasoning, long context, agentic / tool-using work. Heaviest model — only when the task needs it. |
| **qwen3vl** | Text + Image | OCR, screenshot parsing, chart/table reading, UI parsing, visual Q&A. The vision specialist. |
| **qwen3-coder-next** | Code | Code completion, boilerplate, mechanical refactors, syntax fixes. Narrower and faster than qwen3.6 for code-only work. |
| **nomic-embed-text-v2-moe** | Text → vector | **Default embedder.** Multilingual (~100 langs), MoE, Matryoshka dims (768 → 256) — use for new indexes, especially multilingual or storage-conscious. |
| **nomic-embed-text** | Text → vector | English-only / legacy fallback. Keep using for indexes already built on it. |

### Quick decision rules

- Bulk text task (summarize / draft / extract) → `qwen3`
- Routing / classify / triage → `llama3.2:3b` or `phi4-mini:3.8b`
- Image, screenshot, PDF page, chart → `qwen3vl`
- Audio → `gemma3n:e4b`
- Embeddings for search / RAG / dedup → `nomic-embed-text-v2-moe` (default, multilingual); fall back to `nomic-embed-text` only for English-only or legacy indexes
- Mechanical code / boilerplate → `qwen3-coder-next`
- Hard reasoning that you'd still like to offload (rare) → `qwen3.6` with thinking on
- In doubt and the corpus is small → `qwen3`

If the exact model tag fails (`ollama list` doesn't show it), tell the user;
don't silently substitute. Their setup is the source of truth.

## How to invoke

Two ways, in rough order of preference. **Default to the CLI** — it's the
shortest path and works everywhere. **Reach for the helper script** when you
need vision, embeddings, structured JSON output, or to check whether Ollama is
even running.

### CLI (default)

```bash
# One-shot text prompt
ollama run qwen3 "Summarize this email in one sentence: $(cat /path/to/email.txt)"

# Many items via a loop
for f in /path/to/emails/*.txt; do
  echo "=== $f ==="
  ollama run qwen3 "Classify this email as billing | support | sales. Reply with one word only.\n\n$(cat "$f")"
done

# Pipe stdin if the input is large
cat big-doc.txt | ollama run qwen3 "Summarize the above in 5 bullets."
```

The CLI streams. If you're capturing the output for downstream processing,
that's fine — bash collects it before you read it.

### HTTP helper (vision, embeddings, JSON mode, health check)

The helper script lives at `scripts/ollama_call.py`. It uses the stdlib only
and talks to `http://localhost:11434`. It exposes three subcommands:

```bash
# Text chat — prompt on argv or stdin
python scripts/ollama_call.py chat --model qwen3 --prompt "Summarize: ..."

# Vision — pass image paths
python scripts/ollama_call.py chat --model qwen3vl \
  --prompt "Extract all text from this screenshot." \
  --image /path/to/screenshot.png

# JSON mode — force structured output
python scripts/ollama_call.py chat --model qwen3 \
  --prompt "Extract sender, date, amount from this email." \
  --json

# Embeddings
python scripts/ollama_call.py embed --model nomic-embed-text-v2-moe \
  --text "the quick brown fox"

# Health check — exits 0 if Ollama is up and the model is pulled
python scripts/ollama_call.py health --model qwen3
```

Run `python scripts/ollama_call.py --help` for the full surface. The script is
~150 lines and was written to be inspected, not trusted on faith.

### Always sanity-check before a long run

Before launching a 200-item loop, do a single test call with one item, eyeball
the result, then unroll. A 30-second sanity check has paid for itself many
times.

```bash
python scripts/ollama_call.py health --model qwen3 || {
  echo "Ollama isn't reachable or qwen3 isn't pulled. Tell the user."
  exit 1
}
```

## Failure modes to handle

These will happen. The skill works because you handle them deliberately.

- **Ollama daemon not running.** The HTTP call refuses; the CLI hangs or errors.
  Don't retry blindly. Tell the user: *"I was going to delegate this to a local
  model but Ollama isn't responding on `localhost:11434`. Start it with `ollama
  serve` (or open the Ollama app), or I can do this myself — your call."*
- **Model tag not pulled.** Error mentions the model isn't found. Don't
  substitute a different model on your own. Tell the user the exact `ollama
  pull <tag>` command they'd need, or fall back to a model you've already
  verified is there.
- **Local model output is wrong.** For verifiable tasks (JSON schema, code that
  must parse, classification against a ground truth), validate the output and
  retry once with a tightened prompt. If it fails again, escalate to yourself —
  don't ship bad output.
- **Local model is just slow.** That's the trade. If the user is watching and
  it's painful, switch to a smaller model or do the work yourself. Don't sit on
  a slow loop quietly.
- **The corpus is too small to be worth delegating.** Three items isn't bulk.
  Just do it.

## Verifying output

Match the verification effort to the cost of being wrong.

- **Schema'd output (JSON, structured fields):** parse it. If it doesn't parse,
  retry once with a cleaner prompt; if it still fails, do it yourself.
- **Bulk classification:** spot-check 3-5 random items by eye before trusting
  the rest.
- **Free-form summaries / drafts:** read one or two end-to-end. If they read as
  coherent and on-task, the rest are probably fine.
- **Code:** run it (or at least let the user run it) — don't paste local-model
  code into a file without a syntax check.

You don't need to verify every output. You need to verify *enough* that you
trust the batch.

## Communicating with the user

When you delegate, surface it lightly so the user can audit: *"Running qwen3
locally to classify these — back in a moment."* Show the model and (when it
matters) which subset of items you tested before unrolling.

If you decide *not* to delegate when this skill would have suggested it, that's
fine, but say why briefly: *"Doing this one myself — needs full repo context."*
Users develop their own intuition for when to trust your delegation calls; help
them get there.

## Reference files

- `references/recipes.md` — worked end-to-end examples per task type (bulk
  summarize, OCR a PDF, classify 100 tickets, embed-and-search, code
  boilerplate). Read this when you want a pattern to copy.
- `references/cli-quickref.md` — one-line CLI invocations per model. Read this
  when you just need the command.
- `scripts/ollama_call.py` — the HTTP helper. Read it if anything goes wrong;
  it's small enough to understand in one pass.
