# Spec 009: Benchmark Harness

**Status:** draft
**Phase:** v0.4
**Research deps:** research/benchmarks.md §1 (Retrieval Accuracy — targets and methodology), research/benchmarks.md §2 (Latency targets — P50/P95), research/stack.md §0 (Strategic Question — "how do we know it's actually good?")
**Depends on:** Spec 001 (core search engine), Spec 002 (embedding model config), Spec 007 (cross-encoder reranking)
**Blocks:** Spec 010 (verification loops depend on benchmark infrastructure for measurement)
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

CodeSight has no reproducible way to measure whether retrieval and answer quality are improving or regressing. Each change (new embedding model, different chunk size, reranker toggle) is evaluated by "feels better" rather than by numbers. This blocks:

- Proving that hybrid search actually outperforms vector-only retrieval (claimed +22pp Recall@50 — research/benchmarks.md §1.1) [VERIFIED, Grade B]
- Validating that cross-encoder reranking delivers the +17pp Precision@10 improvement (research/benchmarks.md §1.1) [VERIFIED, Grade B]
- Comparing AST chunking vs regex chunking with statistical rigor
- Demonstrating quality to consulting clients in a defensible way

Without a benchmark harness, every claim in the research files remains theoretical. The harness is the bridge between research claims and measured reality.

## Goals

- 75-85 human-verified benchmark queries covering 6 categories (research/benchmarks.md §1.2) [VERIFIED]
- Automated metric computation: Precision@K, Recall@K, NDCG@10, Faithfulness, Hallucination Rate (research/benchmarks.md §1.2) [VERIFIED]
- 8 A/B testing configurations from baseline (vector-only) to full pipeline (hybrid + rerank + AST + JIT) (research/benchmarks.md §1.2) [VERIFIED]
- SQLite-backed results storage for cross-run comparison
- Statistical significance testing via Wilcoxon signed-rank test (n≥30 queries per comparison) (research/benchmarks.md §1.2) [VERIFIED, Grade B]
- CLI interface: `python -m codesight benchmark run|compare|report`

## Non-Goals

- Real-time production monitoring — benchmarks run offline against a fixed corpus
- Automated query generation — the 80-query bank is manually curated with human-verified ground truth
- End-to-end latency testing under load — separate performance testing concern
- Benchmark against external RAG products — internal quality measurement only
- LLM quality comparison across providers — client chooses LLM based on security, not quality ranking

## Solution

The benchmark harness loads a question bank (JSON file with queries and ground-truth chunk IDs), runs each query through a specified pipeline configuration, computes retrieval and answer quality metrics, and stores results in a SQLite database. A comparison tool loads two result sets and runs statistical tests to determine whether differences are significant.

```
benchmark run --config B --corpus ./test-corpus/
    │
    ├── Load question bank (80 queries + ground truth)
    ├── For each query:
    │   ├── Run search() with config B settings
    │   ├── Compute retrieval metrics (Precision@K, Recall@K, NDCG@10)
    │   ├── Run ask() if LLM metrics requested
    │   └── Compute answer metrics (Faithfulness, Hallucination Rate)
    ├── Aggregate metrics across all queries
    └── Store results in SQLite (run_id, config, timestamp, per-query scores)

benchmark compare --run-a <id> --run-b <id>
    │
    ├── Load per-query scores for both runs
    ├── Wilcoxon signed-rank test per metric
    └── Report: mean diff, p-value, significant? (p < 0.05)

benchmark report --run <id>
    │
    └── Print summary table: metric | mean | median | P5 | P95
```

## Core Specifications

**SPEC-001: Question bank**

| Field | Value |
|-------|-------|
| Description | A JSON file containing ~80 benchmark queries, each with a natural language question, expected ground-truth chunk IDs (or file paths + line ranges), query category, and difficulty level |
| Trigger | `benchmark run` command loads the question bank |
| Input | `tests/benchmarks/questions.json` file |
| Output | List of `BenchmarkQuery` objects with `question`, `ground_truth`, `category`, `difficulty` |
| Validation | Each query must have at least one ground-truth chunk; categories must be one of the 6 defined types |
| Auth Required | No |

Acceptance Criteria:
- [ ] Question bank contains 75-85 queries distributed across 6 categories: 20 factoid, 20 code, 15 multi-hop, 10 JIT, 10 negative, 5 adversarial (research/benchmarks.md §1.2) [VERIFIED]
- [ ] Each query has at least one ground-truth result (file path + line range or chunk ID)
- [ ] Negative queries (no answer expected) have empty ground truth and are scored separately
- [ ] Question bank is a JSON file loadable without external dependencies

**SPEC-002: Retrieval metric computation**

| Field | Value |
|-------|-------|
| Description | For each benchmark query, compute Precision@K, Recall@K, and NDCG@10 by comparing search results against ground truth |
| Trigger | Each query execution during `benchmark run` |
| Input | Search results (ranked list of chunks) + ground truth (expected chunks) |
| Output | Per-query scores: `precision_at_k`, `recall_at_k`, `ndcg_at_10` |
| Validation | K is configurable (default: 5 for Precision, 10 for Recall); NDCG uses standard log2 discount |
| Auth Required | No |

Acceptance Criteria:
- [ ] Precision@5 computed for every query with ground truth (research/benchmarks.md §1.2 — target >0.75) [VERIFIED]
- [ ] Recall@10 computed for every query (target >0.90) (research/benchmarks.md §1.2) [VERIFIED]
- [ ] NDCG@10 computed using standard log2 discounting (target >0.70) (research/benchmarks.md §1.2) [VERIFIED]
- [ ] Negative queries (no ground truth) are excluded from retrieval metrics and scored separately for false-positive rate

**SPEC-003: Answer quality metrics (DeepEval + RAGAS)**

| Field | Value |
|-------|-------|
| Description | For queries that include an `ask()` step, compute Faithfulness (RAGAS) and Hallucination Rate (DeepEval) by evaluating the generated answer against the retrieved context |
| Trigger | `benchmark run --include-llm` flag enables LLM-based answer generation and quality scoring |
| Input | Generated answer text + retrieved context chunks + original question |
| Output | Per-query scores: `faithfulness` (0-1), `hallucination_rate` (0-1), `answer_relevancy` (0-1) |
| Validation | Requires an active LLM backend for answer generation; metrics computed via DeepEval and RAGAS libraries |
| Auth Required | Yes (LLM backend for answer generation) |

Acceptance Criteria:
- [ ] Faithfulness (RAGAS) computed — target >0.85 (research/benchmarks.md §1.2) [VERIFIED]
- [ ] Hallucination Rate (DeepEval) computed — target <10% (research/benchmarks.md §1.2) [VERIFIED]
- [ ] Answer Relevancy (RAGAS) computed — target >0.80 (research/benchmarks.md §1.2) [VERIFIED]
- [ ] LLM metrics are skipped when `--include-llm` is not specified (retrieval-only benchmark is the default)

**SPEC-004: Configuration profiles**

| Field | Value |
|-------|-------|
| Description | 8 predefined benchmark configurations (A through H) that represent different pipeline settings, allowing systematic comparison of retrieval strategies |
| Trigger | `benchmark run --config <letter>` selects a configuration |
| Input | Configuration letter (A-H) or custom JSON config file |
| Output | Pipeline configured per the selected profile for the benchmark run |
| Validation | Unknown config letter raises an error listing valid options |
| Auth Required | No (retrieval configs); Yes (configs that include LLM) |

Acceptance Criteria:
- [ ] Selecting Config A applies vector-only retrieval, no reranker, 512-token chunks (research/benchmarks.md §1.2) [VERIFIED]
- [ ] Selecting Config B applies hybrid BM25+vector+RRF, no reranker, 512-token chunks
- [ ] Selecting Config C applies hybrid+RRF with MiniLM-L-6-v2 reranker, 512-token chunks
- [ ] Selecting Config D applies hybrid+RRF with Qwen3-0.6B reranker, 512-token chunks
- [ ] Selecting Config E applies hybrid+RRF with Qwen3-0.6B, 1024-token chunks with 15% overlap
- [ ] Selecting Config F applies hybrid+RRF with Qwen3-0.6B, AST chunking (code) + 512 (text) — requires Spec 004 (tree-sitter)
- [ ] Selecting Config G applies hybrid+RRF+JIT with Qwen3-0.6B, AST+512+JIT — requires v0.6 JIT feature
- [ ] Selecting Config H applies CAG (hot docs in context), no retrieval — requires v0.5 CAG feature
- [ ] Custom config via `--config-file config.json` for non-standard combinations

**SPEC-005: Results storage**

| Field | Value |
|-------|-------|
| Description | Benchmark results are stored in a SQLite database for reproducibility and cross-run comparison |
| Trigger | Completion of each `benchmark run` |
| Input | Run metadata (config, timestamp, corpus path) + per-query metric scores |
| Output | Rows inserted into `benchmark_runs` (run-level) and `benchmark_scores` (per-query) tables |
| Validation | Each run gets a unique `run_id`; duplicate detection by config + corpus + timestamp |
| Auth Required | No |

Acceptance Criteria:
- [ ] Results stored in `tests/benchmarks/results.db` SQLite file
- [ ] `benchmark_runs` table stores: `run_id`, `config_name`, `corpus_path`, `timestamp`, `aggregate_metrics` (JSON)
- [ ] `benchmark_scores` table stores: `run_id`, `query_id`, `precision_at_k`, `recall_at_k`, `ndcg_at_10`, `faithfulness`, `hallucination_rate`, `answer_relevancy`, `latency_ms`
- [ ] Results persist across process restarts — no in-memory-only storage

**SPEC-006: Statistical comparison**

| Field | Value |
|-------|-------|
| Description | Compare two benchmark runs using the Wilcoxon signed-rank test to determine whether the difference in each metric is statistically significant |
| Trigger | `benchmark compare --run-a <id> --run-b <id>` |
| Input | Two `run_id` values from the results database |
| Output | Per-metric comparison: mean difference, p-value, significant at α=0.05 |
| Validation | Both runs must use the same question bank; minimum n=30 paired scores required for valid comparison (research/benchmarks.md §1.2) [VERIFIED, Grade B] |
| Auth Required | No |

Acceptance Criteria:
- [ ] Wilcoxon signed-rank test applied per metric (non-parametric, no normality assumption) (research/benchmarks.md §1.2) [VERIFIED, Grade B]
- [ ] Results show: metric name, run A mean, run B mean, difference, p-value, significant (yes/no at p<0.05)
- [ ] Error if the two runs used different question banks (incomparable)
- [ ] Warning if n<30 paired observations (insufficient statistical power)

**SPEC-007: CLI interface**

| Field | Value |
|-------|-------|
| Description | Three CLI subcommands for running benchmarks, comparing results, and generating reports |
| Trigger | `python -m codesight benchmark <subcommand>` |
| Input | Subcommand + flags |
| Output | Console output with results or report |
| Validation | Unknown subcommand shows help text |
| Auth Required | No (run/compare/report); Yes (if `--include-llm` is used) |

Acceptance Criteria:
- [ ] `python -m codesight benchmark run --config B --corpus ./path/` executes the benchmark
- [ ] `python -m codesight benchmark compare --run-a <id> --run-b <id>` outputs statistical comparison
- [ ] `python -m codesight benchmark report --run <id>` prints summary table (metric, mean, median, P5, P95)
- [ ] `--include-llm` flag enables answer quality metrics (default: retrieval-only)
- [ ] Progress bar shown during benchmark execution

## Edge Cases & Failure Modes

**EDGE-001: Missing ground truth for a query**
- Scenario: A query in the question bank has no ground-truth entries (empty or null)
- Expected behavior: Treat as a negative query — compute false positive rate instead of Precision/Recall
- Error message: none — handled silently via the `category: negative` classification
- Recovery: Automatic

**EDGE-002: Corpus mismatch**
- Scenario: The benchmark corpus has changed since the question bank was curated — some ground-truth file paths no longer exist
- Expected behavior: Log a warning per missing file; exclude affected queries from aggregate metrics; report the number of excluded queries
- Error message: `"WARNING: Ground truth file {path} not found in corpus — excluding query {id} from metrics"`
- Recovery: Re-curate the question bank after corpus changes

**EDGE-003: LLM backend unavailable during --include-llm run**
- Scenario: `--include-llm` is set but the LLM backend is unreachable
- Expected behavior: Retrieval metrics are computed and stored. LLM metrics are set to null for affected queries. A summary warning is printed.
- Error message: `"LLM backend unavailable — retrieval metrics computed, LLM metrics skipped for this run"`
- Recovery: Fix the LLM backend and re-run with `--include-llm`

**EDGE-004: Insufficient queries for statistical comparison**
- Scenario: `benchmark compare` is called on runs with fewer than 30 paired observations
- Expected behavior: Comparison runs but prints a warning that results may not be statistically reliable
- Error message: `"WARNING: Only {n} paired observations — Wilcoxon test requires n≥30 for reliable results"`
- Recovery: Add more queries to the question bank

**EDGE-005: Config requires unimplemented feature**
- Scenario: Running Config F (AST chunking) before Spec 004 is implemented, or Config G (JIT) before v0.6
- Expected behavior: Error naming the missing feature and the spec that provides it
- Error message: `"Config F requires AST chunking (Spec 004). Implement Spec 004 first or use Config A-E."`
- Recovery: Use a config that only requires implemented features

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Question bank size | ~80 queries | Balanced across 6 categories; n≥30 per comparison for Wilcoxon (research/benchmarks.md §1.2) [VERIFIED, Grade B] |
| Default K for Precision | 5 | Matches consulting use case — clients look at top 5 results |
| Default K for Recall | 10 | Standard IR evaluation (research/benchmarks.md §1.2) [VERIFIED] |
| NDCG discount | log2 | Standard IR practice |
| Significance level | α = 0.05 | Standard statistical threshold |
| Minimum sample size | n = 30 | Required for Wilcoxon statistical power (research/benchmarks.md §1.2) [VERIFIED, Grade B] |
| Results database | SQLite | Consistent with the rest of the CodeSight stack; no external database needed |

## Implementation Notes

### Dependencies

Two new optional packages:
- `deepeval>=1.0` — hallucination detection and RAG metrics (research/benchmarks.md §1.2) [VERIFIED, Grade A]
- `ragas>=0.2` — faithfulness, answer relevancy, context precision/recall (research/benchmarks.md §1.2) [VERIFIED, Grade A]

These are added as an optional `[benchmark]` extra: `pip install codesight[benchmark]`. The core library does not depend on them.

### Module Structure

A new `benchmark/` subpackage under `src/codesight/`:
- `benchmark/__init__.py` — CLI entry point
- `benchmark/runner.py` — benchmark execution engine
- `benchmark/metrics.py` — metric computation (retrieval + LLM)
- `benchmark/storage.py` — SQLite results storage
- `benchmark/compare.py` — statistical comparison
- `benchmark/configs.py` — predefined configuration profiles A-H

### Question Bank Format

The question bank is a JSON file at `tests/benchmarks/questions.json`:

```
[
  {
    "id": "factoid-001",
    "question": "What is the default chunk size?",
    "category": "factoid",
    "difficulty": "easy",
    "ground_truth": [
      {"file_path": "src/codesight/chunker.py", "start_line": 15, "end_line": 22}
    ]
  },
  ...
]
```

## Alternatives Considered

### Alternative A: pytest-based benchmarks only

Trade-off: Simpler — just add benchmark tests to the existing test suite.
Rejected because: pytest tests are pass/fail. Benchmarks need aggregate metrics, cross-run comparison, and statistical analysis. A dedicated harness provides these features without cluttering the test suite.

### Alternative B: External benchmark platform (Langfuse + Braintrust)

Trade-off: Richer visualization, team collaboration, hosted storage.
Rejected because: Adds an external dependency and network requirement. CodeSight's "search is 100% local" promise extends to quality measurement. SQLite results are sufficient for a single-engineer project. Langfuse integration can be added later for observability (research/benchmarks.md §1.2 mentions Langfuse) [VERIFIED, Grade A].

### Alternative C: Synthetic query generation (RAGAS generate)

Trade-off: Automatically generate questions from the corpus — no manual curation.
Rejected because: Generated queries may not reflect real consulting use patterns. The 80-query manual bank is curated to cover the specific query types clients ask. Synthetic generation can supplement but not replace human-curated ground truth.

## Open Questions

- [ ] Should benchmark results be stored alongside the main index (same SQLite) or in a separate database? Separate prevents accidental deletion during re-index — @juan
- [ ] Should the CLI output include a Markdown report that can be committed to the repo for historical tracking? — @juan
- [ ] Is 80 queries sufficient for all 8 configs, or should the bank grow to 120+ for better per-category statistical power? — @juan

## Acceptance Criteria

- [ ] Question bank with ~80 queries in 6 categories: factoid, code, multi-hop, JIT, negative, adversarial (research/benchmarks.md §1.2) [VERIFIED]
- [ ] `benchmark run --config B` executes hybrid retrieval benchmark and stores results in SQLite
- [ ] `benchmark run --config A` vs `--config B` shows hybrid outperforms vector-only (research/benchmarks.md §1.1 — +22pp Recall@50) [VERIFIED, Grade B]
- [ ] `benchmark compare` runs Wilcoxon signed-rank test and reports p-values (research/benchmarks.md §1.2) [VERIFIED, Grade B]
- [ ] `benchmark report` prints summary table with mean, median, P5, P95 per metric
- [ ] 8 predefined configs (A-H) matching the research benchmark matrix (research/benchmarks.md §1.2) [VERIFIED]
- [ ] DeepEval + RAGAS compute Faithfulness, Hallucination Rate, Answer Relevancy when `--include-llm` is set
- [ ] Retrieval metric targets: Precision@5 >0.75, Recall@10 >0.90, NDCG@10 >0.70 (research/benchmarks.md §1.2) [VERIFIED]
- [ ] LLM metric targets: Faithfulness >0.85, Hallucination Rate <10% (research/benchmarks.md §1.2) [VERIFIED]
- [ ] `pytest tests/ -x -v` passes (benchmark tests included in the suite)
