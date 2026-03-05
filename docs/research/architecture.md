# Architecture Research — CodeSight

Last updated: 2026-03-04
Review cadence: 90 days
Next review: 2026-06-02

---

## 1. Retrieval Strategies

### 1.1 Hybrid BM25 + Dense Vector Search

**How it works:**
Run BM25 (keyword) and dense vector (semantic) searches in parallel. Fuse results using Reciprocal Rank Fusion (RRF) with k=60. Returns a unified ranked list capturing both exact keyword matches and semantic similarity.

**Evidence:**
- Recall@50 improves from 72% (pure vector) to 94% (+22pp) with only +15ms latency. [VERIFIED, Grade B — BSWEN benchmark, 2026-02-25]
- Hybrid+RRF improves Precision@5 by +17pp over pure BM25 in Elasticsearch. [VERIFIED, Grade C — Elastic vendor source]
- TREC iKAT 2025: fusing first (RRF) then reranking produces superior results vs reranking-then-fusion. [VERIFIED, Grade C — conference proceedings via EmergentMind]

**When to use:**
- Document search with both keyword-specific and conceptual queries
- When Recall is the priority metric

**When NOT to use:**
- Pure semantic similarity tasks (duplicate detection) — vector-only is sufficient
- Extremely low-latency requirements where +15ms matters

**Trade-offs:**
| Pro | Con |
|-----|-----|
| +22pp Recall improvement | Requires both BM25 and vector indexes |
| Only +15ms latency overhead | RRF alone gives marginal NDCG (+0.0085 in one benchmark) |
| No labeled data needed | Must pair with reranking for meaningful precision gains |

### 1.2 Reciprocal Rank Fusion (RRF)

**How it works:**
Score = Σ 1/(k + rank_i) for each ranker i, where k=60. Purely rank-based — ignores raw scores, no normalization needed.

**Evidence:**
- RRF with k=60 is the industry standard. Used by LanceDB, Elasticsearch, Weaviate as default. [VERIFIED, Grade A — multiple vendor docs + Glaforge analysis]
- On WANDS dataset: RRF NDCG = 0.7068 vs BM25 = 0.6983 (+0.0085). Tiered dis_max with boosting achieved 0.7497. [VERIFIED, Grade B — SoftwareDoug]
- Convex Combination (CC) outperforms RRF with even minimal labeled data. CC is sample-efficient. [VERIFIED, Grade A — ACM TOIS peer-reviewed]

**When to use:**
- Default when no labeled data exists
- Zero-config hybrid search setup

**When NOT to use:**
- When labeled relevance data is available (use CC instead)
- When field-level boosting matters

**Trade-offs:**
| Pro | Con |
|-----|-----|
| No training data needed | Marginal NDCG improvement alone |
| Simple implementation | Outperformed by CC with small labeled sets |

### 1.2.1 Sigmoid Reciprocal Rank Fusion (SRRF)

**How it works:**
Replace RRF's linear decay with a sigmoid function: Score = Σ sigmoid(α(β - rank_i)). Amplifies differences between top-ranked and lower-ranked items.

**Evidence:**
- Outperforms standard RRF on HotpotQA and similar multi-hop benchmarks. [VERIFIED, Grade A — peer-reviewed]
- Drop-in replacement for RRF — same inputs, different scoring function.

**When to use:** When RRF's marginal NDCG improvement is insufficient; multi-hop queries.
**When NOT to use:** When RRF already satisfies accuracy requirements (simpler).

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Better multi-hop performance than RRF | Requires tuning α and β hyperparameters |
| Drop-in replacement | Less battle-tested than RRF k=60 |

### 1.3 Cross-Encoder Reranking

**How it works:**
Stage 2 of two-stage retrieval. After hybrid search retrieves top 50-100 candidates, a cross-encoder scores each (query, document) pair. Re-sort by score, take top 10.

**Evidence:**
- Precision@10: 61% → 78% (+17pp) when adding reranker to hybrid search. [VERIFIED, Grade B — BSWEN]
- Precision@10: 0.62 → 0.84 (+22pp) with reranking. [VERIFIED, Grade B — BSWEN reranker benchmark]
- Conservative estimate: +20-40% accuracy improvement. [VERIFIED, Grade B — multiple sources]
- A reranker can only reorder — cannot recover missed documents. [VERIFIED, Grade A — architectural constraint]

**When to use:**
- Always, after Recall@50 exceeds 90%
- Complex/analytical queries (+47-52% improvement)

**When NOT to use:**
- Sub-100ms latency requirements (reranking adds 120-400ms)
- When Recall < 90% (fix retrieval first)

**Trade-offs:**
| Pro | Con |
|-----|-----|
| +17-22pp Precision@10 | +120-400ms latency |
| Works with any retrieval method | Cannot fix recall problems |
| Small models (22M-1.2B params) | CPU inference slow for large candidate sets |

---

## 2. Chunking Strategies

### 2.1 Recursive Character Splitting (Text Documents)

**How it works:**
Split at natural boundaries (paragraphs, sentences, words) with target chunk size. Add overlap between chunks to preserve cross-boundary context.

**Evidence:**
- 400-token chunks: 88.1-89.5% recall — best in Chroma's evaluation. [CORRECTED — Chroma benchmarked at 400 tokens, not 512. Source: research.trychroma.com/evaluating-chunking]
- 1,024-token with 15% overlap: +22% higher answer accuracy than 512 no-overlap on FinanceBench. [VERIFIED, Grade B — dasroot.net]
- Vecta Feb 2026 benchmark: recursive 512 placed first at 69% accuracy vs semantic at 54%. [VERIFIED, Grade B]
- "Context cliff" around 2,500 tokens where quality drops. [VERIFIED, Grade C — dasroot.net]
- Chunking impact is "comparable to or greater than the embedding model itself." [VERIFIED, Grade B — Firecrawl]

**When to use:**
- Default for text documents: 400-512 tokens, 10-20% overlap
- Technical/analytical docs: 1,024 tokens, 15% overlap

**When NOT to use:**
- Code files (use AST-based — §2.2)
- Paginated PDFs (use page-level — §2.3)

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Simple, fast, deterministic | No document structure awareness |
| 88-89% recall at 400 tokens | Overlap increases storage 10-20% |
| 3.2x faster than 2,048-token chunks | May split mid-sentence |

### 2.2 AST-Based Chunking (Code Documents)

**How it works:**
Parse code with tree-sitter to build AST. Chunk at function/class boundaries. Recursively split large nodes. Concatenating chunks reproduces original file. Language-agnostic.

**Evidence:**
- cAST: +4.3 Recall@5 on RepoEval. [VERIFIED, Grade A — arXiv 2506.15655, EMNLP 2025, CMU + Augment Code]
- +2.67 Pass@1 on SWE-bench, +4.2 on RepoEval (StarCoder2-7B). [VERIFIED, Grade A]
- Tested: Python, Java, C#, TypeScript. [VERIFIED, Grade A]
- Open-source: github.com/yilinjz/astchunk [VERIFIED, Grade A]

**When to use:** All code files in the corpus.
**When NOT to use:** Plain text, markdown, prose.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Preserves semantic structure | Requires tree-sitter per language |
| +4.3 Recall@5 | Slightly more complex pipeline |
| Language-agnostic | Chunks vary in size |

### 2.3 Page-Level Chunking (PDFs)

**How it works:** Split at PDF page boundaries.

**Evidence:**
- NVIDIA benchmark: highest average accuracy (0.648), lowest variance. 15% overlap best. [VERIFIED, Grade A — NVIDIA developer blog]

**When to use:** Paginated documents, slide decks.
**When NOT to use:** Long-form text without meaningful page breaks.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Preserves document pagination, highest accuracy (0.648) | Meaningless for non-paginated content |
| Lowest variance across benchmarks | Pages may be too large for some queries |

### 2.4 Multi-Scale Chunk Indexing

**How it works:**
Index the same document at multiple chunk sizes (e.g., 256, 512, 1024 tokens). At query time, search all scales and fuse results with RRF.

**Evidence:**
- +1-37% improvement over single-scale indexing across multiple benchmarks. [VERIFIED, Grade A — AI21 Labs]
- Works because different query types benefit from different granularities.

**When to use:** When queries range from factoid (small chunks) to analytical (large chunks).
**When NOT to use:** Storage-constrained (2-3x index size). Simple use cases where single-scale suffices.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| +1-37% improvement | 2-3x storage and indexing cost |
| No query classification needed | More complex retrieval pipeline |

### 2.5 Hierarchical Parent-Child Chunking

**How it works:**
Small chunks for retrieval precision, but return the parent chunk (larger context) to the LLM. LangChain `ParentDocumentRetriever` implements this.

**Evidence:**
- +18-25% improvement over flat chunking. [VERIFIED, Grade B — LangChain, multiple benchmarks]
- Retrieves precise match, returns surrounding context.

**When to use:** When LLM needs more context than the retrieval unit.
**When NOT to use:** Factoid extraction where small chunks suffice.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| +18-25% over flat chunking | Requires two-level storage |
| Better LLM context | Parent chunk may include irrelevant content |

### 2.6 Late Chunking (JinaAI)

**How it works:**
Embed the full document first with a long-context model, then chunk the embedding into segments. Each chunk embedding retains full-document context.

**Evidence:**
- Demonstrated by JinaAI with jina-embeddings-v3. [VERIFIED, Grade A — arXiv 2409.04701]
- Preserves cross-chunk context without overlap.

**When to use:** When using long-context embedding models (8K+ tokens).
**When NOT to use:** Short-context models, or when chunk independence is required.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| No information loss at chunk boundaries | Requires long-context embedding model |
| No overlap needed | Less mature, fewer implementations |

### 2.7 Domain-Specific Recommendations

| Domain | Size | Overlap | Recall | Source |
|--------|------|---------|--------|--------|
| Technical docs | 1,024 tokens | 20% | 94% | dasroot.net [VERIFIED, Grade B] |
| Legal docs | 2,048 tokens | 15% | 92% | dasroot.net [VERIFIED, Grade B] |
| Financial docs | 1,024 tokens | 15% | 93% | dasroot.net [VERIFIED, Grade B] |
| Factoid queries | 256-512 tokens | 10% | ~89% | Firecrawl/Chroma [VERIFIED, Grade B] |
| Code files | AST-based | N/A | +4.3 Recall@5 | cAST [VERIFIED, Grade A] |

---

## 3. CAG vs RAG

### 3.1 Cache-Augmented Generation (CAG)

**How it works:**
Preload entire knowledge base into LLM context. Cache KV parameters. Query against cached context — no retrieval step.

**Evidence:**
- BERTScore advantage: +1-4% over best RAG variant. [VERIFIED, Grade A — arXiv 2412.15605, ACM WWW 2025]
- Speed: ~40x (2.33s vs 94.35s). [VERIFIED, Grade A]
- Only viable when corpus fits in context window. [VERIFIED, Grade A]
- "Lost in the Middle": accuracy degrades for buried information. [VERIFIED, Grade B]

**When to use:** Small, static corpora (<200K tokens). Speed-critical.
**When NOT to use:** Large/dynamic corpora. Cost-sensitive ($1.25-5.00/query at 1M tokens).

**Trade-offs:**
| Pro | Con |
|-----|-----|
| ~40x faster than RAG (2.33s vs 94.35s) | Only works when corpus fits in context window |
| +1-4% BERTScore over best RAG variant | $1.25-5.00/query at 1M token context |
| No retrieval infrastructure needed | "Lost in the Middle" degrades buried information |

For CodeSight: RAG required at scale. CAG viable for small "hot cache" of frequently-queried docs.

---

## 4. Deployment Patterns

### 4.1 Two-Loop Architecture

Standard enterprise RAG:
- **Ingestion (Offline):** Documents → Chunking → Embedding → Index
- **Inference (Online):** Query → Embed → Hybrid search → RRF → ACL filter → Rerank → LLM → Response

Used by Azure AI Search, Elasticsearch, Weaviate. [VERIFIED, Grade A — Microsoft Learn, Elastic]

**When to use:** Default for all RAG systems. Proven, well-understood, predictable latency.
**When NOT to use:** When corpus changes faster than ingestion lag is acceptable (consider JIT — §4.5).

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Proven pattern, used by all major platforms | Two separate systems to maintain (ingestion + inference) |
| Well-understood latency characteristics | Ingestion lag means stale results for new documents |

### 4.2 Agentic Retrieval (Production-Ready)

LLM-assisted query planning: decompose complex queries into subqueries, parallel multi-source retrieval. Azure AI Search, Glean, Google Agentspace all shipping agentic retrieval in production (2026). [VERIFIED, Grade A — Microsoft Learn, vendor announcements]

A-RAG (arXiv 2602.03442): formal agentic RAG framework with tri-tool interface (search, retrieve, answer). Provides structured approach to multi-hop reasoning. [VERIFIED, Grade A — peer-reviewed]

**When to use:** Complex multi-hop queries, multi-source retrieval.
**When NOT to use:** Simple lookups, when latency must be predictable, cost-sensitive.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Handles complex multi-hop queries automatically | Unpredictable latency per query |
| Parallel multi-source retrieval | Higher cost per query (LLM reasoning overhead) |
| LLM decomposes ambiguous queries | More complex to debug than deterministic pipelines |

### 4.3 GraphRAG

**How it works:**
Build a knowledge graph from documents, then traverse the graph during retrieval for better multi-hop reasoning.

**Evidence:**
- 3.4x accuracy improvement on multi-hop queries vs standard RAG. [VERIFIED, Grade A — Microsoft Research]
- Indexing cost: ~$33K for large corpora (GPT-4-level extraction). [VERIFIED, Grade B]
- HippoRAG: 10-30x cheaper alternative using hippocampal memory model. [VERIFIED, Grade A — arXiv]

**When to use:** Multi-hop reasoning, relationship-heavy domains (legal, medical).
**When NOT to use:** Simple document search. Cost-sensitive. Single-hop queries.

**Trade-offs:**
| Pro | Con |
|-----|-----|
| 3.4x accuracy on multi-hop | ~$33K indexing cost at scale |
| Better relationship reasoning | Complex to maintain graph freshness |
| HippoRAG reduces cost 10-30x | Adds significant pipeline complexity |

For CodeSight: Not recommended for MVP. Consider for enterprise tier with relationship-heavy corpora.

### 4.4 RAG Evaluation Frameworks

Standard tools for measuring RAG pipeline quality:
- **RAGAS**: Open-source, measures faithfulness, answer relevancy, context precision/recall. [VERIFIED, Grade A — GitHub]
- **DeepEval**: Open-source, 14+ metrics including hallucination detection. [VERIFIED, Grade A — GitHub]
- Consensus: "Naive RAG is dead" — production RAG requires evaluation loops, not just build-and-ship. [VERIFIED, Grade B — multiple industry analyses]

For AI/ML security layers (content filtering, guardrails, response verification), see security.md §4.

### 4.5 Just-In-Time (JIT) Context

**How it works:**
Instead of relying solely on pre-indexed embeddings, JIT context pulls fresh data from live sources at query time. Three approaches:

1. **Live connector fetch:** On query, pull current state from source (git repo HEAD, API docs endpoint, Confluence page) → chunk → embed → search — all inline. Guarantees zero staleness at cost of latency.
2. **Hybrid JIT + pre-indexed:** Pre-index stable documents (policies, architecture docs). JIT-fetch volatile sources (active branches, recently-edited pages). Router decides based on source freshness metadata.
3. **Incremental sync with freshness signals:** Background workers poll sources, re-index changed documents within minutes. Not true JIT but achieves near-real-time freshness with pre-indexed latency.

**Evidence:**
- GitHub Copilot and Cursor use JIT context: they read the current file, open tabs, and recent git diff at query time rather than relying on stale indexes. [VERIFIED, Grade B — product analysis]
- Onyx uses incremental connector sync (approach 3) with configurable polling intervals. [VERIFIED, Grade A — Onyx docs]
- Azure AI Search "push API" enables near-real-time indexing but still has ingestion lag. [VERIFIED, Grade A — Microsoft Learn]
- For code repos: git webhooks can trigger re-indexing of changed files within seconds. [VERIFIED, Grade B — standard pattern]

**When to use:**
- Code repositories where files change multiple times per day
- Active documentation (wikis, Confluence, Notion) edited by teams
- Any source where stale embeddings cause incorrect answers

**When NOT to use:**
- Static corpora (legal archives, published papers) — pre-index once
- High-throughput queries where JIT latency is unacceptable (>500ms per source fetch)
- Sources behind rate-limited APIs

**Trade-offs:**
| Pro | Con |
|-----|-----|
| Zero staleness for volatile sources | +200-2000ms latency per JIT source fetch |
| No re-indexing pipeline needed for JIT sources | Cannot do semantic search on JIT content without inline embedding |
| Catches changes between index refreshes | Source API availability becomes a query-time dependency |

**For CodeSight:** Hybrid approach recommended. Pre-index stable docs (architecture, policies, onboarding). JIT-fetch for active code files (git HEAD + recent commits) and recently-edited wiki pages. Use git webhooks + incremental re-indexing as the primary freshness mechanism, with true JIT as fallback for sources that change faster than the re-index interval.

---

## 5. Recommended Architecture

### 5.1 Ingestion (Offline)

```
  Sources ──► Connectors ──► Chunking ──► Embedding ──► LanceDB
                                │              │         (vector + BM25)
                            ┌───┴───┐    nomic-embed        │
                            │Text:  │      v1.5             │
                            │400-   │         │        ACL metadata
                            │512tok │    Code: voyage-       │
                            │overlap│    code-3 or AST   Webhooks for
                            └───────┘    tree-sitter     incremental
                                                         re-indexing
```

### 5.2 Inference (Online) — Adaptive Routing

```
  Query ──► Semantic Cache Check (confidence-gated, source-linked invalidation)
                  │
            ┌─────┴──────┐
            │ Cache Hit   │ Cache Miss
            │ (~50-65%)   │
            ▼             ▼
        Response    Query Router (hybrid cascade)
                    ├── Rules (<1ms, ~70%)
                    ├── Embedding classifier (5-30ms, ~20%)
                    └── LLM fallback (500ms, ~10%)
                          │
              ┌───────────┼───────────┬──────────────┬────────────┐
              ▼           ▼           ▼              ▼            ▼
           CAG        Simple      Code Query    Recent/JIT    Multi-hop
          (<200K      Factoid/                                Complex
          tokens)     Standard
              │           │           │              │            │
          Full docs   Hybrid      Hybrid +      Hybrid +     Agentic:
          in context  BM25+Vec   AST index +   BM25+Vec+    decompose →
          + prompt    + RRF      code embed    RRF + live    parallel
          caching     + Rerank   + Rerank      source fetch  sub-queries
              │           │           │              │            │
              └───────────┴───────┬───┴──────────────┴────────────┘
                                  │
                          ACL Filter (metadata)
                                  │
                          Cross-Encoder Rerank (50→10)
                                  │
                          ┌───────┴────────┐
                          │ Simple          │ Complex
                          ▼                 ▼
                      Haiku 4.5         Sonnet 4.6
                      ($1/$5)           (cached, $0.30/$15)
                          │                 │
                          └────────┬────────┘
                                   ▼
                          Verification Loop
                          ├── HHEM grounding check (<600MB, CPU, ~1.5s)
                          ├── Claude Citations API (source attribution, free)
                          └── Confidence gate (low → retry or "I don't know")
                                   │
                               Response ──► Cache Store (only if confidence > threshold)
```

**Critical design principle**: Hybrid BM25+vector+RRF is the baseline for ALL query types except CAG. The router does NOT choose between "BM25 only" vs "hybrid" — hybrid is always the default. The router only varies: (1) reranking depth, (2) AST index inclusion, (3) JIT source fetch, (4) multi-step decomposition, and (5) LLM tier. Research consistently shows hybrid beats any single strategy (+22pp Recall@50). [VERIFIED, Grade B — BSWEN, multiple benchmarks]

### 5.3 Routing Logic

| Query Type | Detection Signal | Retrieval Strategy | LLM | Latency Budget |
|------------|-----------------|-------------------|-----|----------------|
| Cached repeat | Semantic similarity >0.92 to cached query | None (cache hit) | None | <50ms |
| CAG (hot docs) | Small corpus (<200K tokens), frequently queried | Full docs in Claude context + prompt caching | Sonnet 4.6 (cached) | <200ms |
| Simple factoid | Short query, single entity | Hybrid BM25+vector+RRF → light rerank (top-20→10) | Haiku 4.5 | <300ms |
| Standard search | Default | Hybrid BM25+vector+RRF → full rerank (top-50→10) | Sonnet 4.6 (cached) | <500ms |
| Code question | Code keywords, file references, function names | Hybrid BM25+vector+RRF + AST-chunked index + code embedding → rerank | Sonnet 4.6 | <500ms |
| Recent/JIT | "latest", "recent commit", active branch refs | Hybrid BM25+vector+RRF + JIT source fetch (git HEAD, webhook-updated docs) | Sonnet 4.6 | <1000ms |
| Multi-hop complex | "compare", "how does X relate to Y", compound | Agentic: decompose → parallel hybrid retrieval per sub-query → merge → rerank | Sonnet 4.6 | <2000ms |

Router implementation: hybrid cascade — rule-based patterns (<1ms, catches ~70%), embedding classifier via Semantic Router (5-30ms, catches ~20%), LLM classifier via Haiku (~500ms, catches remaining ~10%). RouteLLM (benchmarks.md §3.4) handles the Haiku vs Sonnet LLM tier selection, achieving 70-85% cost savings. [VERIFIED, Grade A]

Implementation: Semantic Router (`semantic-router==0.1+`) for embedding classifier, RouteLLM for LLM tier selection, custom rules engine for pattern matching. See stack.md §0.5 for component details.

### 5.4 Verification Loop (Post-Generation)

Every response passes through verification before reaching the user. This is the highest-leverage investment for accuracy — verification loops break the compounding error curve (95% per-step × 10 steps = 60% without verification, 97.5% with 95% recovery). [VERIFIED, Grade A — 99-percent-accuracy research]

| Layer | Tool | What It Checks | Latency | Cost |
|-------|------|---------------|---------|------|
| 1. Grounding | HHEM (Vectara) | Is the response supported by retrieved docs? Score 0-1 | ~1.5s CPU | Free (OSS, <600MB) |
| 2. Attribution | Claude Citations API | Does every claim cite a source? | 0ms (part of generation) | Free (cited_text ≠ output tokens) |
| 3. Confidence gate | Custom logic | Citation count, HHEM score, hedging language | <10ms | Free |
| 4. Cache decision | Custom logic | Only cache if confidence > threshold | <1ms | Free |

If HHEM score < 0.5 or no citations for factual claims:
1. Rewrite query and retry retrieval (max 2 retries)
2. If still fails → return "I couldn't find a confident answer" + show raw retrieved chunks
3. Never cache low-confidence responses

For enterprise tier: add NeMo Guardrails (topic containment, PII detection). See security.md §4.

### 5.5 Why This Architecture

1. **Hybrid search for ALL queries** — +22pp Recall over vector-only, no exception. Router varies depth, not strategy.
2. **Semantic cache** — 50-65% of queries served without retrieval or LLM cost (confidence-gated, source-linked invalidation)
3. **Verification loops** — highest-leverage accuracy investment. HHEM + Citations catch hallucinations before they reach the user.
4. **Adaptive routing** — 3-tier cascade (rules → embeddings → LLM) routes in <1ms for 70% of queries
5. **RRF** is zero-config default; upgrade to SRRF or CC when labeled data exists
6. **Cross-encoder** adds +17-22pp Precision for +120-400ms
7. **LanceDB**: embedded, no server, native hybrid search + reranking, millions of vectors
8. **AST chunking** for code: +4.3 Recall@5, no competitor does this
9. **LLM routing**: cheap model (Haiku) for simple queries, Sonnet for complex — 70-85% cost savings
10. **JIT context** for code and volatile docs: webhooks + incremental re-index + live fetch keeps results fresh
11. **CAG for hot docs**: 40x faster, +1-4% quality for small frequently-queried corpora
12. **ACL filter before LLM**: prevents over-permissioning (security.md §1)
13. **Confidence-gated caching**: only cache high-quality answers, source-linked invalidation prevents stale cache

---

## Sources

1. BSWEN, "Hybrid Search vs Reranker", docs.bswen.com (2026-02-25) [Secondary]
2. Glaforge, "Understanding RRF", glaforge.dev (2026-02-10) [Primary]
3. Lian & Wu, "Hybrid Retrieval Fusion", ACM TOIS, dl.acm.org/doi/10.1145/3596512 (2023) [Primary]
4. SoftwareDoug, "ES Hybrid Search", softwaredoug.com (2025-03-13) [Primary]
5. Cheng et al., "Don't Do RAG", arXiv 2412.15605, ACM WWW 2025 [Primary]
6. Jin et al., "cAST", arXiv 2506.15655, EMNLP 2025 [Primary]
7. Chroma, "Evaluating Chunking", research.trychroma.com (2025) [Primary]
8. NVIDIA, "Best Chunking Strategy", developer.nvidia.com (2024) [Primary]
9. dasroot.net, "Chunking Strategies" (2026-02) [Secondary]
10. Firecrawl, "Chunking Strategies for RAG" (2026) [Secondary]
11. Microsoft Learn, "RAG Overview", learn.microsoft.com (2026-02-26) [Primary]
12. Elastic, "Hybrid Search", elastic.co/search-labs (2025-2026) [Secondary]
13. BSWEN, "Best Reranker Models", docs.bswen.com (2026-02-25) [Secondary]
14. AI21 Labs, "Multi-Scale Chunk Indexing", ai21.com (2025-2026) [Primary]
15. JinaAI, "Late Chunking", arXiv 2409.04701 (2024) [Primary]
16. LangChain, "ParentDocumentRetriever", python.langchain.com/docs (2026) [Primary]
17. "A-RAG: Agentic RAG", arXiv 2602.03442 (2026) [Primary]
18. Microsoft Research, "GraphRAG", github.com/microsoft/graphrag (2025-2026) [Primary]
19. HippoRAG, arXiv 2405.14831 (2024) [Primary]
20. RAGAS, "RAG Evaluation", github.com/explodinggradients/ragas (2025-2026) [Primary]
21. DeepEval, "LLM Evaluation", github.com/confident-ai/deepeval (2025-2026) [Primary]
22. "SRRF: Sigmoid RRF", peer-reviewed (2025) [Primary]
23. Onyx, "Connector Sync", docs.onyx.app (2026) [Primary]
24. Microsoft Learn, "Push API for Azure AI Search", learn.microsoft.com (2026) [Primary]
