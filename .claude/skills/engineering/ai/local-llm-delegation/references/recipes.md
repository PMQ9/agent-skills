# Recipes — End-to-End Patterns

Worked examples for the most common delegation jobs. Each recipe shows
which model, the exact commands, and how Claude should consume the output.

## Recipe 1: Bulk summarize a directory of documents

**When:** User has a folder of N items (emails, articles, PDFs already
text-extracted) and wants a one-paragraph summary per item.

**Model:** `qwen3:8b` — reliable instruction-following on summarization.

**Pattern:**

```bash
mkdir -p summaries
for f in input_docs/*.txt; do
  out="summaries/$(basename "${f%.txt}").md"
  [ -f "$out" ] && continue   # resume-safe
  ollama run qwen3:8b "Summarize the following document in one paragraph.
Focus on what action, if any, the reader should take.

$(cat "$f")" > "$out"
done
```

**Verification:** Read 2 random outputs end-to-end. If they're coherent and
on-topic, ship the batch. If one is wildly off, retry that item with a
tightened prompt rather than re-doing all of them.

**Notes:** The `[ -f "$out" ] && continue` makes this resumable if Ollama
crashes mid-run. For corpora over ~100 items, prefer this over a single
long-running command.

---

## Recipe 2: OCR a scanned PDF

**When:** User uploads a scanned PDF (or screenshots) and wants the text out.

**Model:** `qwen3-vl:8b` for the OCR pass.

**Pattern (page-by-page):**

```bash
# 1. Render each page to PNG (requires poppler's pdftoppm)
mkdir -p pages
pdftoppm -png -r 200 input.pdf pages/page

# 2. OCR each page
mkdir -p text
for img in pages/page-*.png; do
  out="text/$(basename "${img%.png}").txt"
  python scripts/ollama_call.py chat --model qwen3-vl:8b \
    --prompt "Transcribe all visible text from this page. Preserve paragraph breaks. Do not summarize or paraphrase." \
    --image "$img" > "$out"
done

# 3. Concatenate
cat text/page-*.txt > full_transcript.txt
```

**Verification:** Open the first page of the PDF and the first text file
side-by-side. Counts and proper nouns are easiest to spot-check. For legal
or medical scans, escalate to a dedicated OCR (Tesseract, Document AI) —
qwen3-vl is good but not certified.

---

## Recipe 3: Classify a CSV with hundreds of rows

**When:** User has a CSV and wants a new column with a categorical label.

**Model:** `llama3.2:3b` — classification is the cheapest shape of task. If
the 3B model misclassifies in your spot check, step up to `qwen3:8b` (and
re-do the rows it already labeled).

**Pattern:**

```bash
# Assume input.csv has columns: id, subject, body
# We want: id, subject, body, category

python3 << 'PY'
import csv, json, subprocess

with open("input.csv") as fin, open("output.csv", "w") as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames + ["category"])
    writer.writeheader()
    for row in reader:
        prompt = (
            "Classify this support ticket as one of: billing, technical, sales, other. "
            "Reply with one word only.\n\n"
            f"Subject: {row['subject']}\nBody: {row['body']}"
        )
        result = subprocess.run(
            ["ollama", "run", "llama3.2:3b", prompt],
            capture_output=True, text=True, timeout=60,
        )
        row["category"] = result.stdout.strip().lower().split()[0]
        writer.writerow(row)
PY
```

**Verification:** Run `cut -d, -f<category-column> output.csv | sort | uniq -c`
and check that the distribution looks plausible (no single category at 99%
unless the input is genuinely that skewed). Then spot-check 5 random rows.

---

## Recipe 4: Build a semantic search index with embeddings

**When:** User has hundreds or thousands of text items and wants
"find me the ones similar to this query."

**Model:** `nomic-embed-text-v2-moe` (default, multilingual) — or `nomic-embed-text:v1.5` if you're appending to an existing English-only index.

**Pattern:**

```bash
# 1. Embed every item
python3 << 'PY'
import json, subprocess
items = [line.strip() for line in open("items.txt") if line.strip()]
out = []
for it in items:
    res = subprocess.run(
        ["python", "scripts/ollama_call.py", "embed", "--text", it],
        capture_output=True, text=True, check=True,
    )
    out.append({"text": it, "vector": json.loads(res.stdout)})
with open("index.jsonl", "w") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
PY

# 2. Search by cosine similarity
python3 << 'PY'
import json, subprocess, sys
query = sys.argv[1]
qv = json.loads(subprocess.check_output(
    ["python", "scripts/ollama_call.py", "embed", "--text", query]
))
def cos(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5
    nb = sum(x*x for x in b) ** 0.5
    return dot / (na * nb)
hits = []
with open("index.jsonl") as f:
    for line in f:
        r = json.loads(line)
        hits.append((cos(qv, r["vector"]), r["text"]))
hits.sort(reverse=True)
for s, t in hits[:10]:
    print(f"{s:.3f}\t{t}")
PY "your query here"
```

**Verification:** The top 1-3 results should be obviously relevant. If they're
not, either the embedding model is wrong for this domain (try a domain-specific
embedder) or the items are too short / too long.

**Note:** For >10k items, move the cosine search to a real vector store
(pgvector, sqlite-vec, faiss). The above is fine for ~thousands.

---

## Recipe 5: Generate boilerplate code from a spec

**When:** User describes a small, mechanical code artifact (a Pydantic model,
a SQLAlchemy table, a TypeScript interface, a CRUD handler stub).

**Model:** `qwen3-coder-next` — narrower than qwen3.6, faster.

**Pattern:**

```bash
ollama run qwen3-coder-next "Generate a TypeScript interface and a zod schema
for these fields:

- id: UUID (string)
- email: string, valid email
- created_at: ISO datetime string
- subscription_tier: 'free' | 'pro' | 'enterprise'
- monthly_spend_cents: non-negative integer

Output only the code in one fenced block. Use camelCase." > generated.ts
```

**Verification:** Run the file through the relevant compiler/linter (`tsc
--noEmit generated.ts`, `python -c 'import generated'`, etc.). If it doesn't
parse, retry once with `"The previous attempt didn't compile; here's the
error: <paste>. Fix and reissue the full file."` If it still fails, write
it yourself.

---

## Recipe 6: Pre-filter a large corpus before Claude reads it

**When:** User points at 500 documents and asks Claude a question about
them. Loading all 500 into your context is wasteful (and may not fit).

**Pattern:**

1. **Embed everything** with `nomic-embed-text-v2-moe` (Recipe 4 above).
2. **Rank by similarity** to the user's question.
3. **Triage the top ~30** with `llama3.2:3b`: "Is this document relevant
   to '<question>'? YES or NO."
4. **Hand the resulting ~10 to yourself** to read carefully.

This turns "Claude reads 500 docs" (expensive, might not fit) into
"Claude reads 10 docs that the local stack pre-filtered." The user gets
the same quality answer for a fraction of the cost.

**Verification:** If the answer feels thin, widen the YES set in step 3 and
re-read. If you suspect the embedding ranking missed something, ask the
user to name a doc that should have been in the top 10 and trace why it
wasn't.
