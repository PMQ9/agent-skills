---
name: rag-architecture
description: Design and implement retrieval-augmented generation systems — chunking strategies, embedding choices, hybrid search, reranking, contextual retrieval, query rewriting, citation handling, evaluation, and the failure modes that quietly degrade RAG quality over time. Use this skill whenever the task involves grounding an LLM in a document corpus, building a search-over-documents feature, debugging a RAG system that "works in the demo but not in prod," choosing between RAG and long-context or fine-tuning, designing a pipeline that ingests new documents, or any work where the phrase "the model needs access to our docs" comes up. Trigger on terms like "RAG," "retrieval," "vector search," "embeddings," "knowledge base," "search over documents," "chatbot over our wiki," and similar — even when the user does not name RAG explicitly.
---

# RAG Architecture

Retrieval-augmented generation is conceptually simple — fetch relevant documents, put them in the prompt — and operationally a swamp. Most RAG systems work great on a curated demo corpus and get progressively worse as the corpus grows, the queries diversify, and the index ages. This skill is about the architectural choices that determine whether RAG keeps working at scale.

## When to use RAG (and when not to)

RAG is the right answer when:

- The corpus is large enough that it cannot fit in context, or fitting it would be prohibitively expensive.
- The corpus changes frequently — daily, weekly — and re-indexing is cheaper than retraining.
- You need citation/attribution: the user wants to know *which document* an answer came from.
- The corpus is sensitive (per-user data, per-tenant access controls) and cannot be baked into a model.

Reach for alternatives when:

- The corpus fits in context. With prompt caching, putting the whole corpus in the system prompt is often cheaper, faster, and higher quality than RAG. This applies to corpora up to roughly 100K-500K tokens for most use cases.
- The task is about *style* or *behavior*, not *facts*. Fine-tuning beats RAG for "always respond in our brand voice."
- The "questions" are actually structured queries. If users ask "show me orders from last Tuesday over $500," that's SQL, not RAG.
- The corpus is a graph or a knowledge base with strong relational structure. Graph-aware retrieval beats embedding similarity for connected-data questions.

A useful test: if you can describe a query type that RAG should handle but obviously will struggle with (multi-hop, aggregation, temporal), that query type is a signal RAG alone is not the architecture. Hybridize.

## The pipeline at a glance

Every RAG system has these stages, even if some are degenerate:

1. **Ingestion.** Documents enter the system, get parsed and normalized.
2. **Chunking.** Documents are split into retrievable units.
3. **Indexing.** Chunks are embedded and/or indexed for keyword search.
4. **Query understanding.** User input is transformed into one or more queries.
5. **Retrieval.** Candidate chunks are fetched.
6. **Reranking.** Candidates are reordered by relevance.
7. **Generation.** Final chunks are inserted into a prompt and the model answers.
8. **Citation/post-processing.** Sources are surfaced; output is validated.

Get each stage right and the system works. Skipping or under-investing in any one stage is how RAG quality dies.

## Ingestion and parsing

The unsexy stage that determines the ceiling for everything downstream. Bad parsing → bad retrieval, no matter how good your embeddings are.

For PDFs: do not use `pdftotext` and stop there. Modern pipelines use layout-aware parsers (Unstructured, LlamaParse, Azure Document Intelligence, AWS Textract) that preserve tables, headings, and reading order. PDFs with multi-column layouts, tables, or scanned pages especially need this.

For HTML: strip navigation, ads, and boilerplate. Preserve semantic structure (headings, lists, tables) — they help chunking and reranking.

For code: parse by syntactic structure (tree-sitter, language servers), not by line count. A function should be one chunk; a class can be one chunk or several.

For tables and structured data: convert to a representation the embedding model can reason about. Markdown tables work well for small tables; for large tables, consider row-level chunks with column headers replicated, or store the table in a structured store and retrieve whole tables.

Always preserve metadata: source URI, document title, section, page number, timestamp, author. You'll need these for citations, filtering, and freshness logic later.

## Chunking

The single most important choice in a RAG pipeline, and the one most teams underthink.

Bad defaults that kill quality:

- Fixed-size chunks (e.g., 512 tokens) split mid-sentence, mid-table, mid-code-block.
- No overlap between chunks. The query keyword lands on a chunk boundary and gets missed.
- One-size-fits-all chunking applied to a heterogeneous corpus.

Better strategies, in roughly increasing sophistication:

**Semantic chunking by structure.** Split on headings, paragraphs, list items, function definitions. Most documents have native semantic boundaries — use them. Add a small overlap (50-100 tokens) to handle boundary cases.

**Recursive chunking.** Try to split at the largest semantic boundary that produces chunks under the size limit. If a section is too big, split by paragraph; if a paragraph is too big, split by sentence.

**Hierarchical chunking.** Index at multiple granularities — section-level, paragraph-level, sentence-level. Retrieve at the level that matches the query. Useful for corpora with long structured documents (textbooks, legal documents).

**Late chunking.** Embed the whole document, then chunk based on embedding similarity within the document. Computationally expensive but produces chunks aligned with how the embedding model "sees" the text.

**Contextual chunking (Anthropic's contextual retrieval).** Before embedding each chunk, prepend a 1-2 sentence context generated by an LLM ("This chunk is from the Q3 earnings call, discussing revenue by region, in the context of comparing year-over-year growth"). This dramatically improves retrieval on chunks that don't make sense in isolation. Cost: one LLM call per chunk at ingestion time. Worth it for corpora where chunks reference earlier parts of a document.

Chunk size: there's no universally right number. 256-1024 tokens is the working range for most embedding models. Smaller chunks → more precise retrieval but more chunks per answer; larger chunks → more context per chunk but more noise. Tune based on eval results, not vibes.

## Embeddings

Pick an embedding model based on:

- **Domain match.** General-purpose models (OpenAI ada-3, Cohere embed-v3, Voyage AI) work for most domains. Specialized domains (code, biomedical, legal) often benefit from domain-specific embeddings.
- **Multilingual needs.** Not all embedding models handle non-English well. Test on real queries in real languages.
- **Dimension.** Higher dimensions cost more storage and compute; the gain over a well-chosen smaller embedding is often small. 768-1536 is the typical range.
- **Self-hosted vs API.** API embeddings are easier; self-hosted is cheaper at scale and avoids data egress. Hybrid (cache API embeddings) is common.

Reembed when you change models. Embeddings from different models live in incompatible spaces — you cannot mix them in one index. This means migrating embedding models is a full reindex. Plan accordingly.

Asymmetric embedding (different models for queries vs documents) used to be standard; modern unified models mostly remove the need. Read your model's docs — some still recommend a `query: ` / `passage: ` prefix or distinct endpoints.

## Hybrid search

Pure vector search loses to hybrid (vector + keyword) on essentially every benchmark. Run both, fuse the results.

Why: vector search captures semantic similarity but misses exact-match cases (product codes, error messages, names, technical terms). Keyword search (BM25, lexical) handles exact matches but misses paraphrase. Together they cover both.

Implementation:

- Run both retrievers in parallel, each returning top-K (K typically 20-50).
- Fuse with Reciprocal Rank Fusion (RRF) or weighted score blending. RRF is parameter-free and robust; weighted blending requires score normalization but is tunable.
- Pass the fused candidates to the reranker.

Many vector databases (Weaviate, Vespa, Elasticsearch with vectors) support hybrid natively. If yours doesn't, run two stores and fuse in application code — it's a 30-line function.

## Reranking

The retrieval stage optimizes for *recall* — get the right chunk into the candidate set, somewhere. The reranker optimizes for *precision* — put the right chunk at the top.

A reranker takes (query, candidate) pairs and assigns relevance scores using a cross-encoder model that attends to both jointly. It is more accurate than embedding similarity (which compares pre-computed vectors) but more expensive (one model call per candidate, no precomputation).

The standard pipeline:

```
query → retrieve top 50 (cheap, fast) → rerank to top 5 (expensive, accurate) → generate
```

Rerankers worth knowing: Cohere Rerank, BGE rerankers, Jina Reranker, voyage-rerank. LLM-based reranking (asking a small LLM to score candidates) also works and gives you a knob for domain prompting.

A reranker is the single highest-leverage addition to a basic vector-search RAG. If you don't have one, add one before tuning anything else.

## Query understanding

The user's question is rarely the optimal query for retrieval. Two failure modes:

1. **Underspecified queries.** "What about the second one?" makes no sense out of context.
2. **Overspecified queries.** "I need to know if our 2023 expense policy section 4.2 paragraph 3 applies to international travel reimbursements above $500." The literal query has too much noise.

Treatments:

**Query rewriting.** An LLM rewrites the query into a search-optimal form. Especially valuable for chat-style RAG where context disambiguates.

**Multi-query.** Generate N rephrasings of the query, retrieve for each, fuse the results. Improves recall on hard queries; trades retrieval cost for quality.

**HyDE (hypothetical document embeddings).** Have the LLM generate a hypothetical answer to the query, embed *that*, and search. The hypothetical answer is structurally closer to the documents you're searching for than the question is. Effective when queries and documents have very different surface forms.

**Decomposition.** For multi-part queries, break into subqueries, retrieve for each, combine. The "compare X and Y" query becomes a "find X" + "find Y" pair.

Don't apply all of these at once. Each adds latency and cost; pick the ones your eval shows actually help.

## Filtering and access control

Many real-world RAG systems need to filter retrieval by metadata: per-user, per-tenant, per-permission, per-time-window. Two patterns:

**Pre-filter.** Apply metadata filters before vector search. Most production vector DBs support this; performance varies wildly by DB and selectivity. With strict filters and large corpora, pre-filter performance can be terrible if the index isn't designed for it.

**Post-filter.** Vector search first, then filter results. Simpler but can return zero results when filters are aggressive.

Always pre-filter for security/access control. A post-filter that drops chunks the user shouldn't see is one bug away from leaking them. A pre-filter that excludes them from the search at all is safer.

## Citations

If users will see RAG outputs, they need citations. Citations serve three purposes: trust, verification, and debugging. Make them first-class.

Two citation patterns:

**Inline citations.** The model produces text with citation markers `[1]`, `[2]` mapped to source chunks. Requires prompting the model to cite, and validating that citations correspond to retrieved chunks.

**Highlight-based citations.** After generation, run a separate pass that aligns generated claims to source spans. More robust against hallucinated citations, more expensive.

Validate citations programmatically. The model will sometimes cite a chunk that doesn't actually contain the claim. A simple check (does the cited chunk even exist? does it contain the keywords from the cited claim?) catches the worst cases. A semantic check (does the cited chunk entail the claim?) catches more, at higher cost.

## Faithfulness

Faithfulness — the answer is supported by the retrieved context, not hallucinated — is the central RAG quality metric. Two failure modes:

1. **Hallucination.** Model invents facts not in the context.
2. **Mixing.** Model uses retrieved context plus its own training data, producing answers that look grounded but aren't.

Mitigations:

- Prompt explicitly: "Answer only based on the provided context. If the answer is not in the context, say so." This helps but is not sufficient.
- Provide an "I don't know" pathway. Models will hallucinate to avoid saying "I can't find that." A structured output with `{answer | cannot_answer}` reduces this.
- Post-generation verification. A second LLM call asks "is this answer supported by these sources?" and rejects answers it can't verify. Doubles cost; catches the worst hallucinations.
- For high-stakes applications, require citations and verify them (see above).

## Evaluation

A RAG system has multiple things to measure, and conflating them hides regressions:

**Retrieval metrics** (does the right chunk get retrieved?):
- Recall@K — is the gold chunk in the top K? Usually the most actionable retrieval metric.
- MRR — at what rank does the first relevant chunk appear?
- nDCG — relevance-weighted ranking quality.

**Generation metrics** (given retrieved chunks, is the answer good?):
- Faithfulness — is the answer supported by the chunks?
- Answer relevance — does the answer address the question?
- Completeness — does the answer use all the relevant retrieved info?

**End-to-end metrics**:
- Task success rate against a curated golden set.
- User satisfaction proxies in production (thumbs up/down, follow-up rate).

Build the eval set early. Hand-curate 50-200 (query, gold answer, gold chunks) tuples representative of real usage. Synthetic evals (LLM-generated Q&A from your docs) supplement but don't replace real queries. See `llm-evaluation`.

Evaluate retrieval and generation separately. A drop in answer quality might be a retrieval regression, a generation regression, or both — and the fix is different in each case.

## Freshness and updates

Static corpora are rare. Plan from day one:

- **Incremental indexing.** Add/remove/update chunks without rebuilding the whole index. Most vector DBs support this; verify before committing.
- **Source of truth.** The vector DB is a derived index, not the source. Keep canonical documents in their own store. Reindex from source on schema or model changes.
- **Stale detection.** Track per-document timestamps; surface stale results with a freshness indicator or filter them out for time-sensitive queries.
- **Reindex triggers.** Document changed → re-chunk and re-embed *that document* (not the whole corpus). Embedding model changed → full reindex.

Without these, RAG quality decays silently. Last week's earnings report is still in the index alongside this week's; the model cites the wrong one; nobody notices for a month.

## Long context vs RAG

Modern models handle 100K-1M token contexts. This raises the question: why RAG?

RAG still wins when:
- Corpus is too large for context, period.
- Per-query cost matters more than per-query quality.
- You need fine-grained access control or citations.
- You need fast iteration on retrieval logic without changing the model.

Long context wins when:
- The corpus fits and isn't too expensive.
- Multi-document reasoning is critical (RAG fragments documents).
- Dev velocity matters more than serving cost.

A hybrid pattern: RAG to narrow to a working set of, say, 50K tokens, then put the working set in long context for the model to reason over. This combines RAG's selectivity with long-context reasoning.

## Anti-patterns

**The chunk-and-pray pipeline.** Fixed-size chunks, default embedding, top-K vector search, no reranker, no query rewriting, no eval. Works on a curated demo, falls over on real queries.

**The mystery embedding upgrade.** Team upgrades embedding model to "the new better one" without reindexing or evaluating. Half the index is in the old space, half the new — retrieval is broken in subtle ways.

**The 100-chunk prompt.** "Just put the top 100 results in the prompt and let the model figure it out." The model does worse with 100 chunks than with 5. Reranking + smaller K wins.

**The PDF-to-text-to-embeddings pipeline.** Layout is destroyed at parse time. Tables become word salad. Retrieval works on the demo doc but fails on every PDF with a real layout.

**The same-K for everything.** Top-5 chunks for "what's the CEO's name" and top-5 for "summarize all our 2023 product launches." Different queries need different breadth.

**The unmonitored index.** No metrics on what's retrieved, no log of what's never returned, no signal when retrieval quality regresses. The system rots silently.

**The unfiltered shared index.** All tenants in one index without metadata filtering, "we'll add access control later." A retrieval bug becomes a data breach.

## Related skills

- `llm-application-engineering` for the LLM-call infrastructure RAG generates against
- `llm-evaluation` for measuring RAG quality
- `agent-design` for retrieval-as-tool patterns where the agent decides when to search
- `prompt-injection-defense` — retrieved documents are an injection vector
