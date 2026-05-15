# CLI Quick Reference

One-liners per model. Copy and adapt. Assumes Ollama daemon is running.

## llama3.2:3b — triage, routing

```bash
# Yes/no relevance check
ollama run llama3.2:3b "Is this email about billing? Reply only YES or NO.\n\n$(cat email.txt)"

# Three-way classification
ollama run llama3.2:3b "Classify as billing | support | sales. One word.\n\n$(cat ticket.txt)"
```

## qwen3:8b — general-purpose text

```bash
# Summarize
ollama run qwen3:8b "Summarize in 3 bullets:\n\n$(cat doc.txt)"

# Structured extraction (use HTTP helper for guaranteed JSON)
python scripts/ollama_call.py chat --model qwen3:8b --json \
  --prompt "Extract {sender, date, amount_usd} as JSON from this email:\n$(cat email.txt)"
```

## phi4:14b — mid-weight reasoning

```bash
# Use when qwen3:8b's output looked sloppy but qwen3.6:35b would be overkill
ollama run phi4:14b "Walk through whether this code change is safe under concurrent writes:\n\n$(cat diff.patch)"
```

## qwen3.6:35b — hard reasoning, long context, agentic

```bash
# Reasoning with thinking mode
ollama run qwen3.6:35b "/think Plan a migration from MySQL to Postgres for a 2TB table with FK constraints and live writes."

# Long-context summarization (feed a whole book chapter)
cat chapter.txt | ollama run qwen3.6:35b "Outline the main argument and identify the three weakest claims."
```

## qwen3-vl:8b — vision

```bash
# OCR a screenshot
python scripts/ollama_call.py chat --model qwen3-vl:8b \
  --prompt "Transcribe every word visible in this screenshot. Preserve layout where possible." \
  --image screenshot.png

# Extract a table from an image
python scripts/ollama_call.py chat --model qwen3-vl:8b --json \
  --prompt "Extract this table as a JSON array of row objects." \
  --image table.png
```

## gemma3n:e4b — audio + lightweight multimodal

```bash
# Audio transcription (Ollama supports audio via the chat API for gemma3n)
python scripts/ollama_call.py chat --model gemma3n:e4b \
  --prompt "Transcribe this audio verbatim." \
  --image recording.wav   # despite the name, --image attaches any media file

# Quick image caption on a low-RAM box
python scripts/ollama_call.py chat --model gemma3n:e4b \
  --prompt "One-sentence caption." \
  --image photo.jpg
```

(Note: confirm with `ollama list` whether the gemma3n build on this machine
supports audio — some packagings ship vision-only. If audio fails, fall back
to a dedicated whisper.cpp / faster-whisper install.)

## qwen3-coder-next — narrow code tasks

```bash
# Generate a Pydantic model from a column list
ollama run qwen3-coder-next "Generate a Pydantic v2 model named Invoice with these fields:
id: int, customer_email: EmailStr, amount_cents: int, paid_at: datetime | None.
Use proper imports. Code only, no commentary."

# Mechanical refactor
ollama run qwen3-coder-next "Rename every 'user_id' to 'account_id' in this file. Output the full file.\n\n$(cat handlers.py)"
```

## nomic-embed-text-v2-moe (default) / nomic-embed-text — embeddings

```bash
# Single embedding to stdout (JSON array)
python scripts/ollama_call.py embed --model nomic-embed-text-v2-moe --text "billing dispute about overage charges"

# Embed many lines into a JSONL of {text, vector}
while IFS= read -r line; do
  vec=$(python scripts/ollama_call.py embed --model nomic-embed-text-v2-moe --text "$line")
  printf '{"text": %s, "vector": %s}\n' "$(jq -Rs . <<<"$line")" "$vec"
done < lines.txt > embeddings.jsonl
```

## Health check before a long run

```bash
python scripts/ollama_call.py health --model qwen3:8b || {
  echo "ollama or qwen3:8b unavailable — tell the user before starting"
  exit 1
}
```
