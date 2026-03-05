# Spec 007: Cross-Encoder Reranking

**Status:** done
**Phase:** v0.3
**Research deps:** research/stack.md §4 (Cross-Encoder Rerankers), research/benchmarks.md §1 (Retrieval Accuracy), research/architecture.md §1 (Retrieval Strategies)
**Depends on:** Spec 001 (search pipeline), Spec 002 (embedding quality improves reranker input)
**Blocks:** None
**Created:** 2026-02-28
**Updated:** 2026-03-04

## Problem

After RRF merge, the top K results are ranked by combining BM25 and vector scores independently. Neither method reads the query and chunk together — BM25 counts keyword matches, vector search compares embeddings. The ranking can therefore be wrong: a chunk that superficially matches keywords might outrank a chunk that actually answers the question.

A cross-encoder reranker reads the query AND each candidate chunk as a pair, producing a much more accurate relevance score. External benchmarks show adding a reranker to hybrid search improves Precision@10 by +17-22pp (research/benchmarks.md §1.1) [VERIFIED, Grade B]. For consulting engagements, this is the difference between "the answer is usually in the top 5" and "the answer is almost always #1."

## Goals

- Add optional cross-encoder reranking step after RRF merge — off by default, opt-in
- Use local models only (no API) — maintains the "search is 100% local" promise
- Precision@10 improvement of +17pp or more on a benchmark query set vs hybrid-without-reranker (research/benchmarks.md §1.1) [VERIFIED, Grade B]
- Configurable: two model tiers — fast dev model, higher-quality prod model
- Configurable enable/disable for speed-sensitive deployments

## Non-Goals

- API-based rerankers (Cohere Rerank, Voyage Rerank) — add later if clients request
- Reranking at indexing time — reranking is query-time only
- Replacing RRF — reranking complements it, runs after it
- Always-on reranking — adds +120-400ms per query; opt-in by default (research/benchmarks.md §2) [VERIFIED, Grade B]

## Solution

Reranking is inserted as a post-RRF step. The pipeline expands the RRF candidate set (top 20 instead of top K), feeds each (query, chunk) pair to the cross-encoder model, re-sorts by reranker score, and returns the top K.

```
Without reranking:
  query → BM25 top 20 → ┐
                         ├→ RRF merge → top K → done
  query → Vector top 20 → ┘

With reranking (CODESIGHT_RERANKER=true):
  query → BM25 top 20 → ┐
                         ├→ RRF merge → top 20 → cross-encoder → top K → done
  query → Vector top 20 → ┘
```

The reranker can only reorder what retrieval already found — it cannot recover missed documents. This means Recall must be ≥90% before reranking is meaningful (research/architecture.md §1.3) [VERIFIED, Grade A]. Hybrid search achieves 94% Recall@50 (research/benchmarks.md §1.1) [VERIFIED, Grade B], satisfying this prerequisite.

## Core Specifications

**SPEC-001: Reranking pipeline insertion**

| Field | Value |
|-------|-------|
| Description | When enabled, cross-encoder reranking is inserted between RRF merge and final top-K return |
| Trigger | `search()` or `ask()` call when `CODESIGHT_RERANKER=true` |
| Input | Query string + top 20 RRF results (chunk text + metadata) |
| Output | Top K results re-sorted by cross-encoder score, replacing RRF score |
| Validation | At least 1 result from RRF (empty list is no-op) |
| Auth Required | No |

Acceptance Criteria:
- [ ] `CODESIGHT_RERANKER=true` inserts reranking between RRF merge and result return
- [ ] `CODESIGHT_RERANKER=false` (default) skips reranking entirely — zero overhead, no behavior change
- [ ] Reranking applies to both `search()` and `ask()` pipelines
- [ ] Results are re-sorted by cross-encoder score; original RRF rank is discarded

**SPEC-002: Reranker model selection**

| Field | Value |
|-------|-------|
| Description | `CODESIGHT_RERANKER_MODEL` selects which cross-encoder model to use |
| Trigger | First reranking call (model loaded lazily and cached for the process lifetime) |
| Input | `CODESIGHT_RERANKER_MODEL` env var |
| Output | Loaded `CrossEncoder` model instance; auto-downloaded if not present |
| Validation | Any HuggingFace model ID is accepted; validated on load |
| Auth Required | No |

Acceptance Criteria:
- [ ] Default model is `ms-marco-MiniLM-L-6-v2` (22.7M params, dev-tier speed) (research/stack.md §4.3) [VERIFIED, Grade A]
- [ ] `CODESIGHT_RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B` loads the production model (MTEB-R 65.80, research/stack.md §4.2) [VERIFIED, Grade A]
- [ ] Model is downloaded once on first use and cached in the sentence-transformers cache directory
- [ ] Model is loaded once per process and reused across all searches (no per-query reload)

**SPEC-003: Candidate set size**

| Field | Value |
|-------|-------|
| Description | RRF produces an expanded candidate set (top N) which the reranker re-scores before final top-K return |
| Trigger | Every reranked search |
| Input | `CODESIGHT_RERANKER_TOP_N` (default: 20) |
| Output | `CODESIGHT_RERANKER_TOP_N` candidates scored; top K returned to caller |
| Validation | Must be ≥ K (final result count); integer |
| Auth Required | No |

Acceptance Criteria:
- [ ] Default candidate set is 20 (top 20 RRF results fed to reranker)
- [ ] `CODESIGHT_RERANKER_TOP_N` is configurable via env var
- [ ] If RRF returns fewer than `RERANKER_TOP_N` candidates, all available candidates are reranked

**SPEC-004: Latency budget**

| Field | Value |
|-------|-------|
| Description | Reranking latency overhead per search stays within the budget for the configured model |
| Trigger | Every reranked search |
| Input | Top 20 candidate chunks + query |
| Output | Reranked results within latency budget |
| Validation | Measured in tests on reference hardware |
| Auth Required | No |

Acceptance Criteria:
- [ ] `ms-marco-MiniLM-L-6-v2` reranking 20 chunks on CPU: observed latency ≤ 400ms (research/benchmarks.md §2 — "200-400ms CPU estimate") [VERIFIED, Grade C]
- [ ] `Qwen3-Reranker-0.6B` reranking 20 chunks: latency ≤ 2000ms on CPU, ≤ 500ms on GPU (to be confirmed by internal benchmark)
- [ ] Reranker disabled → zero latency overhead, identical pipeline timing to non-reranker code path

## Edge Cases & Failure Modes

**EDGE-001: Reranker model not cached**
- Scenario: `CODESIGHT_RERANKER=true` on first run; model files not on disk
- Expected behavior: Auto-download on first use via sentence-transformers; log download progress
- Error message: `"[INFO] Downloading reranker model ms-marco-MiniLM-L-6-v2... (first use only)"` — not an error, informational
- Recovery: Automatic; subsequent runs use cached model

**EDGE-002: Empty chunk content**
- Scenario: A chunk in the RRF top-20 results has empty or whitespace-only content
- Expected behavior: Skip that chunk from the reranker input; preserve its original RRF position at the tail of results
- Error message: No user-facing error; log at DEBUG level
- Recovery: Automatic

**EDGE-003: Very short query**
- Scenario: User submits a 1-2 word query (e.g., "payment" or "auth")
- Expected behavior: Reranker runs normally; may produce minimal reordering improvement; no error
- Error message: None
- Recovery: N/A — short queries are valid inputs; reranking is harmless even if improvement is small

**EDGE-004: Reranker disabled**
- Scenario: `CODESIGHT_RERANKER=false` (default) — no reranker model is loaded
- Expected behavior: Pipeline is identical to pre-reranker behavior; no model is initialized; no memory allocated for reranker
- Error message: None
- Recovery: N/A

**EDGE-005: Concurrent search calls**
- Scenario: Multiple simultaneous `search()` calls when reranker is enabled
- Expected behavior: Reranker model is initialized once and shared across calls; inference is thread-safe
- Error message: None
- Recovery: N/A

**EDGE-006: Apple Silicon (MPS) acceleration**
- Scenario: Running on an M-series Mac with MPS available
- Expected behavior: sentence-transformers automatically uses MPS backend for inference; latency improves vs CPU
- Error message: None
- Recovery: N/A — automatic device detection

**EDGE-007: Reranker model download failure**
- Scenario: `CODESIGHT_RERANKER=true` on first run but the machine has no internet access and the model is not cached
- Expected behavior: Model download fails; reranking is disabled for this session with a warning; search results use RRF ranking only
- Error message: `"Reranker model download failed — reranking disabled for this session. Pre-download the model on a machine with internet access."`
- Recovery: Pre-download the model on a connected machine; the sentence-transformers cache directory can be copied to the target machine

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Reranker enabled (default) | `false` | Opt-in to avoid breaking existing behavior; adds +120-400ms (research/benchmarks.md §2) [VERIFIED, Grade B] |
| Dev model | `ms-marco-MiniLM-L-6-v2` | 22.7M params, 74.30 nDCG on TREC DL, instant on CPU (research/stack.md §4.2) [VERIFIED, Grade A] |
| Prod model | `Qwen/Qwen3-Reranker-0.6B` | 0.6B params, MTEB-R 65.80, best accuracy in 0.6B class, Apache 2.0 (research/stack.md §4.2, §4.3) [VERIFIED, Grade A] |
| Candidate set (RERANKER_TOP_N) | 20 | Balances reranker quality vs latency; recommended pipeline: retrieve 50-100 → rerank to 10 (research/benchmarks.md §1.1) [VERIFIED, Grade B] |
| Expected Precision@10 improvement | +17pp (61% → 78%) | BSWEN benchmark; alternative benchmark shows +22pp (0.62 → 0.84) (research/benchmarks.md §1.1) [VERIFIED, Grade B] |

## Implementation Notes

The `_rerank()` function in `search.py` accepts a query string, list of `SearchResult` objects, and target top-K. It uses the `CrossEncoder` class from `sentence-transformers` (already installed as an existing dependency — no new packages required). The model is module-level singleton, loaded lazily on first reranking call.

Configuration additions to `config.py`: `reranker: bool = False`, `reranker_model: str = "ms-marco-MiniLM-L-6-v2"`, `reranker_top_n: int = 20`. RRF merge in `search.py` produces `RERANKER_TOP_N` candidates when reranker is enabled, `top_k` candidates when disabled — the pipeline is otherwise unchanged.

`SearchResult.score` is overwritten with the cross-encoder score when reranking is active. The original RRF score is not preserved in the return value (callers see only the final ranked score).

## Alternatives Considered

### Alternative A: API-based reranker (Cohere Rerank)

Trade-off: Better accuracy (1457 ELO for Cohere Rerank 3.5), managed service, no local GPU needed. Cost: $2/1K queries (research/stack.md §4.2) [VERIFIED, Grade A].
Rejected because: Breaks "search is 100% local" promise. Document chunks would be sent to Cohere's servers. Can be added as optional backend later.

### Alternative B: Replace RRF with learned fusion

Trade-off: Train a model to combine BM25 + vector scores optimally — better than RRF in theory.
Rejected because: Requires query-relevance training data specific to each document collection. Not practical for consulting where each engagement has different documents.

### Alternative C: Always-on reranking

Trade-off: Better results for everyone; simpler config.
Rejected because: Adds +120-400ms to every search (research/benchmarks.md §2) [VERIFIED, Grade B]. Some deployments prioritize speed. Opt-in is the safer default for a new feature.

### Alternative D: LanceDB built-in CrossEncoderReranker

Trade-off: Single `.rerank()` call in search chain; native integration with LanceDB's vector store (research/stack.md §3.2) [VERIFIED, Grade A].
Rejected for now: Would tighten coupling to LanceDB's API and require refactoring the search pipeline. Can be migrated to in a future cycle when we upgrade to Lance SDK 1.0.0.

## Open Questions

- [ ] Should the reranker be enabled by default once internally validated on CodeSight's test query set? — @juan
- [ ] Is 20 candidates optimal? Benchmark 10 vs 20 vs 50 to find quality/latency sweet spot — @juan
- [ ] Should `SearchResult.score` preserve both the original RRF score and the reranker score, or just the final score? — @juan

## Acceptance Criteria

- [ ] `CODESIGHT_RERANKER=true` enables cross-encoder reranking after RRF
- [ ] `CODESIGHT_RERANKER=false` (default) skips reranking — zero overhead, no behavior change
- [ ] Default model `ms-marco-MiniLM-L-6-v2` auto-downloads on first use and is cached
- [ ] `CODESIGHT_RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B` loads the production model (research/stack.md §4.2) [VERIFIED, Grade A]
- [ ] Reranker processes top-N RRF results, returns top K re-sorted by cross-encoder score
- [ ] Search latency increase ≤ 400ms for 20 chunks on CPU (research/benchmarks.md §2) [VERIFIED, Grade C]
- [ ] Works with both `search()` and `ask()` pipelines
- [ ] Precision@10 improves ≥ +17pp on benchmark query set vs hybrid-without-reranker (research/benchmarks.md §1.1) [VERIFIED, Grade B]
- [ ] `pytest tests/ -x -v` passes with reranker both enabled and disabled
