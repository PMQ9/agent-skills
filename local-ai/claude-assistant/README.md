# Local LLM Stack — Claude's Co-Workers

A small fleet of local models that Claude Code / Claude / Cowork can offload
simpler or bulk tasks to (document processing, image parsing, embeddings, quick
codegen, etc.). Pick the smallest model that fits the job.

> **Claude-facing skill:** the routing logic, invocation recipes, and helper
> script live in
> [`.claude/skills/engineering/ai/local-llm-delegation/`](../../.claude/skills/engineering/ai/local-llm-delegation/).
> That's what Claude reads when it decides whether to delegate. This README is
> the human-facing summary — keep the model list here and in `SKILL.md` in sync.

## Setup checklist (one-time)

1. **Install Ollama:** https://ollama.com (macOS app or `brew install ollama`).
2. **Start the daemon:** open the Ollama app, or run `ollama serve`. The skill
   talks to `http://localhost:11434`.
3. **Pull the models you want.** If a tag on your machine differs from the
   table below, edit `SKILL.md` to match — the skill explicitly tells Claude
   not to substitute models silently.

```bash
ollama pull llama3.2:3b
ollama pull phi4-mini:3.8b
ollama pull gemma3n:e4b
ollama pull qwen3
ollama pull qwen3.6              # verify exact tag (may be qwen3:32b or similar)
ollama pull qwen3vl              # verify exact tag (may be qwen2.5vl)
ollama pull qwen3-coder-next     # verify exact tag (may be qwen3-coder)
ollama pull nomic-embed-text-v2-moe
ollama pull nomic-embed-text     # optional: keep for English-only / legacy indexes
```

4. **Verify with the helper:**

```bash
python .claude/skills/engineering/ai/local-llm-delegation/scripts/ollama_call.py health
python .claude/skills/engineering/ai/local-llm-delegation/scripts/ollama_call.py health --model qwen3
```

## Selection Table

| Model | Modality | Strengths | Best for |
|---|---|---|---|
| **llama3.2:3b** / **phi4-mini:3.8b** | Text | Tiny, fast triage model | Cheap routing ("is this relevant?"), classification, fast cleanup — keeps bigger models free for harder work |
| **gemma3n:e4b** | Text + Image + Audio | Small, efficient, fully multimodal incl. audio | Audio transcription/understanding, quick image captions, lightweight Q&A |
| **qwen3.6** | Text + Tools + Thinking, long-context | Agentic coding specialist; supports tool use and toggleable thinking mode | Repo-level coding, multi-file edits, tool-using agents, reasoning-heavy work |
| **qwen3** | Text | Reliable general-purpose instruction follower | Summarization, drafting, structured extraction, JSON / tool-call shaping |
| **qwen3vl** | Text + Image | Vision-language specialist (OCR, layout, charts, UI) | Document processing, screenshot/UI parsing, image-to-text, visual QA |
| **nomic-embed-text-v2-moe** | Text → vector | Multilingual (~100 languages), MoE, Matryoshka dims (768 → 256) for lighter indexes | Default for new RAG / semantic search work, especially multilingual corpora or storage-conscious setups |
| **nomic-embed-text** | Text → vector | English-leaning, larger input context, smaller footprint | English-only RAG, legacy indexes already built on it, lightweight setups |
| **qwen3-coder-next** | Code | Coder-line Qwen3, smaller/faster than 3.6 for narrow code tasks | Code completion, boilerplate, mechanical refactors, syntax fixes |

## Quick Decision Guide

- **Routing / classification / "is this relevant?" / tiny cleanup** → `llama3.2:3b` or `phi4-mini:3.8b`
- **Plain text task (summarize, draft, extract)** → `qwen3`
- **Agentic / repo-level / reasoning-heavy coding** → `qwen3.6`
- **Narrow, fast code task (completion, boilerplate, mechanical refactor)** → `qwen3-coder-next`
- **Hard reasoning / long-context work (non-code)** → `qwen3.6` with thinking mode on
- **Needs to look at an image / screenshot / PDF page** → `qwen3vl`
- **Needs to listen to audio** → `gemma3n:e4b`
- **Need vectors for search or RAG (default, multilingual, or new index)** → `nomic-embed-text-v2-moe`
- **Need vectors for English-only / legacy / lightweight index** → `nomic-embed-text`
- **Tight on RAM / want low latency / multimodal in one shot** → `gemma3n:e4b`

## Notes for Claude

- These models are local — prefer them for bulk / repetitive / privacy-sensitive
  work that doesn't need frontier reasoning.
- For anything ambiguous, judgment-heavy, or requiring deep tool use, do the
  work yourself instead of delegating.
- Embeddings (`nomic-embed-text-v2-moe`) are cheap — use freely to pre-filter
  large corpora before reading.
