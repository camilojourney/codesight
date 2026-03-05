# Research Index — CodeSight

Last updated: 2026-03-04
Review cadence: 30 days (updated whenever any research file changes)
Next review: 2026-04-03

## Status Tracker

| File | Scope | Updated | Cadence | Next Review | Status |
|------|-------|---------|---------|-------------|--------|
| [stack.md](stack.md) | Embedding models, LLMs, vector DBs, rerankers, deployment | 2026-03-04 | 30d | 2026-04-03 | Fresh |
| [benchmarks.md](benchmarks.md) | Retrieval accuracy, latency, cost projections, hallucination | 2026-03-04 | 30d | 2026-04-03 | Fresh |
| [market.md](market.md) | Market size, competitors, pricing, differentiation | 2026-03-04 | 60d | 2026-05-03 | Fresh |
| [architecture.md](architecture.md) | Retrieval patterns, chunking, CAG vs RAG, JIT context, deployment | 2026-03-04 | 90d | 2026-06-02 | Fresh |
| [security.md](security.md) | Access control, auth, data protection, guardrails, compliance | 2026-03-04 | 60d | 2026-05-03 | Fresh |

Status legend: **Fresh** (within cadence) | **Stale** (past cadence) | **Critical** (past 2x cadence)

## Verification Summary

| Tag | Count | Notes |
|-----|-------|-------|
| [VERIFIED] | ~135 | Claims confirmed from primary or 2+ secondary sources (includes Round 3 implementation research) |
| [CORRECTED] | 8 | MiniLM CPU latency (2 docs not 20), chunking recall (400 tokens not 512), LanceDB Tantivy sync-only (not async), SOC 2 cost ranges (both valid), Qwen3-Embedding MTEB (multilingual not English), LanceDB Cloud status (GA not beta), MVP cost range ($115-205 matches breakdown), architecture.md routing (BM25-only→hybrid for all) |
| [UNVERIFIED] | ~13 | Cross-encoder +33.1% (no DOI), Cohere embed-v4 MTEB, 50K doc ACL threshold, Qwen3-Reranker 380ms CPU, Zerank-2 #1 ranking, semantic cache 0.92 threshold (theoretical), M365 webhook renewal patterns |
| [PHANTOM] | 0 | No phantom claims found |

Evidence grades: A (~45%), B (~35%), C (~15%), D (<5%)

## Research Method

4-phase pipeline per RESEARCH-Blueprint/06-research-agents.md:

### Round 1 (2026-03-04)
1. **GATHER** — 5 parallel agents, 100+ web sources, 70+ findings
2. **CROSS-VALIDATE** — 2 verification agents, 28 priority claims checked
3. **SYNTHESIZE** — Files rewritten to template spec
4. **AUDIT** — 2 audit agents: internal consistency + template compliance. 5 inconsistencies fixed, 6 template issues resolved

### Round 2 (2026-03-04)
1. **GATHER** — 5 parallel agents, 85+ new findings (embeddings/VDBs, LLMs/rerankers, retrieval/chunking, market/competitors, security/compliance)
2. **CROSS-VALIDATE** — 2 verification agents, 30 priority claims checked. 24 VERIFIED, 2 CORRECTED, 2 UNVERIFIED, 0 CONTRADICTED
3. **SYNTHESIZE** — All 6 files updated with Round 2 findings: new competitors, new CVEs, advanced chunking strategies, JIT context, cost optimization techniques, EU AI Act deadline
4. **AUDIT** — 2 audit agents: internal consistency + template compliance. 3 inconsistencies found and fixed (LanceDB Cloud beta→GA, MVP cost range alignment, missing +22pp benchmark row). 6/6 files template-compliant, 0 critical issues

### Round 3 — Implementation Research (2026-03-04)
1. **GATHER** — 5 parallel agents focused on implementation: CAG+Semantic Cache, JIT+M365 Connector, Query Router, Agentic RAG+Verification Loops, Benchmarking Framework
2. **SYNTHESIZE** — Implementation guide written to `~Projects/App-Development/REASEARCH/from_scratch.md`. Architecture.md §5 rewritten: fixed routing gap (hybrid for ALL queries, not BM25-only for simple), added verification loop layer (§5.4). Stack.md updated with semantic cache (§0.4) and query router (§0.5). Benchmarks.md §1.2 expanded with full testing framework.
3. **ARCHITECTURE FIX** — User identified critical gap: routing diagram sent "simple factoid" queries to "BM25 only", contradicting research showing hybrid always wins (+22pp Recall). Fixed: hybrid BM25+vector+RRF is now baseline for ALL query types. Router only varies reranking depth, AST inclusion, JIT fetch, and LLM tier.
4. **NEW COMPONENTS** — 5 new decisions added (semantic cache, query router, verification loops, benchmarking framework, M365 connector). Roadmap.md restructured around adaptive architecture phases. Vision.md updated with multi-strategy differentiator.

## How to Use This Research

1. Before writing a spec: read the relevant research files
2. Every claim in a spec must cite a research section: `(research/stack.md §2.1)`
3. If research doesn't cover what you need: update research first, then write the spec
4. After research update: check all dependent specs for stale claims
5. Only use [VERIFIED] Grade A-B claims for spec acceptance criteria
6. [UNVERIFIED] claims OK for directional decisions but must be flagged

## Key Decisions Summary

| # | Decision | Choice | Why | Section |
|---|----------|--------|-----|---------|
| 0 | **Retrieval strategy** | **Adaptive: CAG + RAG + JIT + Agentic** | JIT wins <500 pages (+1-4% quality, 40x speed). RAG required >500 pages (cost, ACL, scale). Adaptive router picks per query. | stack.md §0 |
| 1 | Embedding model | nomic-embed-text-v1.5 (self-hosted) | Matches OpenAI quality, Apache 2.0, $384/mo on g4dn.xlarge | stack.md §1 |
| 2 | LLM backend | Claude Sonnet 4.6 + prompt caching (5-min default, 1hr extended) | Best quality/cost, 78% savings with caching | stack.md §2 |
| 3 | Vector database | LanceDB (embedded, Lance SDK 1.0.0) | No server, native hybrid search + reranking, free OSS | stack.md §3 |
| 4 | Reranker | MiniLM (dev) → Qwen3-Reranker-0.6B (prod) | +17-22pp Precision@10, Apache 2.0 | stack.md §4 |
| 5 | Retrieval | Hybrid BM25+vector → RRF → rerank for ALL queries | +22pp Recall, +17pp Precision. No BM25-only path. SRRF as upgrade. | architecture.md §1, §5.2 |
| 6 | Code chunking | AST via tree-sitter (cAST) | +4.3 Recall@5, language-agnostic | architecture.md §2.2 |
| 7 | Text chunking | Recursive 400-512 tokens, 10-20% overlap | 88-89% recall at 400 tokens | architecture.md §2.1 |
| 8 | Access control | Metadata filters → SpiceDB for enterprise | Enforce at retrieval layer. SpiceDB used by OpenAI. | security.md §1 |
| 9 | Auth | Keycloak 26.4 (self-hosted) / Auth0 (SaaS) | Free + Authlib for FastAPI OIDC. FAPI 2.0, DPoP, passkeys. | security.md §2 |
| 10 | Deployment | Uvicorn --workers + Docker + health checks | Gunicorn deprecated, --limit-max-requests, python:3.12-slim | stack.md §5 |
| 11 | Freshness | JIT context: pre-index stable + webhook re-index + live fetch | Zero staleness for volatile sources. M365 Graph API delta queries. | architecture.md §4.5 |
| 12 | Cost optimization | Prompt caching + semantic caching + LLM routing | 78% (caching) + 70-85% (routing) individually; compound effect TBD | benchmarks.md §3.4 |
| 13 | **Semantic cache** | FAISS (dev) → Redis+RediSearch (prod), threshold 0.92 | 50-65% hit rate, confidence-gated, source-linked invalidation | stack.md §0.4 |
| 14 | **Query router** | Hybrid cascade: rules → embedding → LLM | <1ms for 70% of queries. Semantic Router + RouteLLM. | stack.md §0.5, architecture.md §5.3 |
| 15 | **Verification loops** | HHEM + Claude Citations + confidence gate | Highest-leverage accuracy investment. Breaks compounding error curve. | architecture.md §5.4 |
| 16 | **Benchmarking** | DeepEval + RAGAS + SQLite + Wilcoxon tests | 80-query bank, 8 configs, 3 testing phases | benchmarks.md §1.2 |
| 17 | **M365 connector** | msgraph-sdk + azure-identity, delta queries + webhooks | First external data source. Education endpoints for testing. | from_scratch.md §4 |

## Open Questions

- [ ] Cohere embed-v4 MTEB score (65.2) — unverified from primary source
- [ ] Cross-encoder +33.1% claim — blog cites MIT paper with no DOI
- [ ] Pre-filter ACL degradation threshold — "50K docs" has no verifiable source
- [ ] LanceDB Tantivy FTS: incremental indexing falls back to flat search — timeline for fix?
- [ ] arXiv 2511.15759 defense framework — preprint, awaiting peer review
- [ ] CAG viability for "hot cache" — needs prototype validation
- [ ] Qwen3-Reranker-0.6B CPU latency (~500ms estimated in stack.md) — no independent source confirms exact number
- [ ] Zerank-2 as #1 reranker — vendor claim only, Zerank-1 leads independent boards
- [ ] EU AI Act: does CodeSight's RAG qualify as "high-risk AI"? Legal review needed before Aug 2026
- [ ] Semantic cache poisoning: SAFE-CACHE defense needs prototype validation
- [ ] What is CodeSight's baseline hallucination rate without verification loops?
- [ ] Optimal semantic cache similarity threshold — 0.92 is theoretical, needs empirical validation
- [ ] M365 webhook renewal automation — 30-day max expiration, needs auto-renew
