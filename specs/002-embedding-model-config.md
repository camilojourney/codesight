# Spec 002: Embedding Model Configuration

**Status:** done
**Phase:** v0.3
**Research deps:** research/stack.md §1 (Embedding Models), research/benchmarks.md §1 (Retrieval Accuracy)
**Depends on:** Spec 001 (core search engine)
**Blocks:** Spec 007 (reranking quality depends on embedding quality)
**Created:** 2026-02-24
**Updated:** 2026-03-04

## Problem

The current default embedding model (`all-MiniLM-L6-v2`, 384 dims, 256-token context) limits search quality. Its short context window truncates longer document chunks, and 384 dimensions restrict semantic precision. Users asking "What are the payment terms?" may miss relevant chunks because the embedding doesn't capture enough meaning.

Better local models exist — free, still laptop-runnable, significantly improving retrieval especially for document search where chunks contain longer paragraphs. Some clients also want maximum quality via a cloud API. Both must be supported as a configuration choice.

## Goals

- Upgrade default embedding model to `nomic-embed-text-v1.5` — 768 dims, 8K context, MTEB 62.28% (research/stack.md §1.2, §1.3) [VERIFIED, Grade A]
- Allow model selection via `CODESIGHT_EMBEDDING_MODEL` with allowlist validation — invalid names fail fast
- Support optional API embedding backend for clients who want maximum quality (research/stack.md §1.2) [VERIFIED, Grade A]
- Safe model switching: detect dimension mismatch between stored index and configured model, force rebuild automatically
- Backward compatible: `all-MiniLM-L6-v2` continues to work for existing indexes

## Non-Goals

- Multiple models simultaneously — one model per index, switching requires rebuild
- Fine-tuning embedding models — pre-trained only
- Custom model hosting (vLLM-style) — local sentence-transformers or API, nothing in between
- Ollama embeddings — sentence-transformers has better model selection and MPS acceleration

## Solution

Two independent env var axes:

**Axis 1 — Backend** (`CODESIGHT_EMBEDDING_BACKEND`): `local` (default) runs sentence-transformers on CPU/GPU — no API key, no internet, no cost, no data leaves. `api` calls OpenAI text-embedding-3-large — best quality (3072 dims), but data goes to OpenAI.

**Axis 2 — Model** (`CODESIGHT_EMBEDDING_MODEL`): selects which specific model within the backend. Validated against an allowlist — unknown names fail at startup.

On every load, the stored model name + dimensions in index metadata are compared against the currently configured model. Mismatch forces a full rebuild with a logged warning.

## Core Specifications

**SPEC-001: Default model upgrade**

| Field | Value |
|-------|-------|
| Description | Default embedding model is `nomic-embed-text-v1.5` producing 768-dim vectors with 8K token context |
| Trigger | Any call to `index()` or `search()` when no `CODESIGHT_EMBEDDING_MODEL` is set |
| Input | Document text or query string |
| Output | 768-dimensional float vector |
| Validation | Model downloaded on first use; confirmed available before indexing begins |
| Auth Required | No |

Acceptance Criteria:
- [ ] Unset `CODESIGHT_EMBEDDING_MODEL` uses `nomic-embed-text-v1.5` by default
- [ ] Output vectors are 768-dimensional (research/stack.md §1.2 — "768 (MRL 64-768)") [VERIFIED, Grade A]
- [ ] Model accepts up to 8192 tokens per chunk without truncation (research/stack.md §1.2) [VERIFIED, Grade A]

**SPEC-002: Model allowlist validation**

| Field | Value |
|-------|-------|
| Description | Only explicitly allowlisted models may be configured; any other value is rejected at startup |
| Trigger | Application startup or first embedding call |
| Input | `CODESIGHT_EMBEDDING_MODEL` env var value |
| Output | `ValueError` with list of valid options, or proceeds normally |
| Validation | Case-sensitive string match against allowlist |
| Auth Required | No |

Acceptance Criteria:
- [ ] Valid model name proceeds without error
- [ ] Invalid model name raises `ValueError` listing all valid options before any embedding attempt
- [ ] Allowlist includes at minimum: `nomic-embed-text-v1.5`, `all-MiniLM-L6-v2`, `mxbai-embed-large`, `jina-embeddings-v2-base-code` (local); `text-embedding-3-large` (API)

**SPEC-003: Dimension mismatch detection**

| Field | Value |
|-------|-------|
| Description | If configured model dimensions differ from what was used to build the existing index, a full rebuild is triggered automatically |
| Trigger | `index()` call or application startup when an existing index is detected |
| Input | Stored `model_name` + `dimensions` from index metadata vs. current config |
| Output | Warning log message + automatic full rebuild; existing index is replaced |
| Validation | Compare stored dims (integer) against model's known dims |
| Auth Required | No |

Acceptance Criteria:
- [ ] Switching from `all-MiniLM-L6-v2` (384 dims) to `nomic-embed-text-v1.5` (768 dims) triggers automatic rebuild with logged warning
- [ ] Index metadata (`repo_meta` table) stores model name and dimension count after every successful index operation
- [ ] No silent mismatch — rebuild is always logged at WARNING level

**SPEC-004: API embedding backend**

| Field | Value |
|-------|-------|
| Description | When `CODESIGHT_EMBEDDING_BACKEND=api`, embed document chunks via OpenAI text-embedding-3-large |
| Trigger | Any `index()` call with `CODESIGHT_EMBEDDING_BACKEND=api` |
| Input | Document chunks as text strings; `OPENAI_API_KEY` from environment |
| Output | 3072-dimensional float vectors (research/stack.md §1.2 — "3072 (MRL)") [VERIFIED, Grade A] |
| Validation | API key present; network reachable; response dimension matches expected |
| Auth Required | Yes — `OPENAI_API_KEY` required |

Acceptance Criteria:
- [ ] `CODESIGHT_EMBEDDING_BACKEND=api` with valid `OPENAI_API_KEY` produces 3072-dim vectors
- [ ] Missing `OPENAI_API_KEY` produces error naming the exact env var required, before any network call
- [ ] Large batches are split into groups of 512 texts with progress logging (prevents API payload limits)
- [ ] `search()` remains 100% local even when indexing used the API backend

## Edge Cases & Failure Modes

**EDGE-001: Model not installed**
- Scenario: `CODESIGHT_EMBEDDING_MODEL` is set to a valid allowlisted name but the model files are not present on disk
- Expected behavior: Attempt auto-download via sentence-transformers; if download fails (no internet), raise with clear message
- Error message: `"Model 'nomic-embed-text-v1.5' not found locally. Install via: python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"nomic-embed-text-v1.5\")' or run pip install sentence-transformers first."`
- Recovery: User runs download command or sets `CODESIGHT_EMBEDDING_MODEL=all-MiniLM-L6-v2` for the pre-cached fallback

**EDGE-002: API backend with no internet**
- Scenario: `CODESIGHT_EMBEDDING_BACKEND=api` but network is unavailable
- Expected behavior: API call times out; clear error suggesting local backend
- Error message: `"OpenAI embedding API unreachable. Set CODESIGHT_EMBEDDING_BACKEND=local to use a local model with no network dependency."`
- Recovery: Switch to local backend

**EDGE-003: API rate limit**
- Scenario: OpenAI API returns 429 during batch embedding
- Expected behavior: Exponential backoff — wait 1s, retry; wait 2s, retry; wait 4s, retry; fail after 3 attempts
- Error message: `"OpenAI embedding API rate limited after 3 retries. Reduce batch size or wait before re-indexing."`
- Recovery: Reduce batch size; wait and retry

**EDGE-004: Dimension mismatch mid-indexing**
- Scenario: Index exists with different dimensions but `index()` is called without clearing first
- Expected behavior: Full rebuild is triggered automatically; old index data is discarded; rebuild logged at WARNING
- Error message: `"[WARNING] Embedding model changed (all-MiniLM-L6-v2 384d → nomic-embed-text-v1.5 768d). Rebuilding index from scratch."`
- Recovery: Automatic — no user action needed; rebuild completes normally

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Default model | `nomic-embed-text-v1.5` | MTEB 62.28%, 768 dims, 8K context, Apache 2.0, self-hostable (research/stack.md §1.3) [VERIFIED, Grade A] |
| Fallback model | `all-MiniLM-L6-v2` | 384 dims, 256-token context — backward compatible for existing indexes |
| API model | `text-embedding-3-large` | 3072 dims, $0.13/1M tokens — best quality (research/stack.md §1.2) [VERIFIED, Grade A] |
| Batch size (API) | 512 texts | Prevents payload limits; balances throughput vs. API constraints |
| Allowlist size | 4 local + 1 API | Only tested, verified models — prevents typos from causing silent quality degradation |

## Implementation Notes

The `EmbeddingBackend` protocol (in `embeddings.py`) has two implementations: `LocalBackend` (sentence-transformers) and `APIBackend` (OpenAI). Both expose the same `embed(texts)` / `embed_query(query)` interface. The `config.py` module holds the allowlist and resolves dimensions from model name at startup. Dimension storage lives in the `repo_meta` table in `metadata.db`.

Optional dependency: `openai>=1.0` is gated behind `pip install codesight[openai]` to avoid requiring it for local-only deployments.

## Alternatives Considered

### Alternative A: Always use API embeddings

Trade-off: Best quality, but requires API key, costs money (~$0.13/1M tokens), and sends document content to OpenAI.
Rejected because: Contradicts the "search is 100% local" privacy story. Must remain optional.

### Alternative B: Ollama for embeddings

Trade-off: Unified with LLM backend, single process.
Rejected because: sentence-transformers has better model selection, more mature MPS/CUDA acceleration, and the embedding API surface is simpler (research/stack.md §1.3) [VERIFIED, Grade A].

## Open Questions

- [ ] Should we auto-detect Apple Silicon and recommend `mxbai-embed-large` for M-series chips? — @juan
- [ ] Should model download happen at `pip install` time or first use? — @juan

## Acceptance Criteria

- [ ] `CODESIGHT_EMBEDDING_MODEL=nomic-embed-text-v1.5` produces 768-dim vectors (research/stack.md §1.2) [VERIFIED, Grade A]
- [ ] `CODESIGHT_EMBEDDING_MODEL=all-MiniLM-L6-v2` still works (backward compatibility)
- [ ] Invalid model name raises `ValueError` listing valid options before any I/O
- [ ] Index metadata stores model name + dims; changing model triggers auto-rebuild with WARNING log
- [ ] `CODESIGHT_EMBEDDING_BACKEND=api` uses `text-embedding-3-large`, requires `OPENAI_API_KEY`
- [ ] Missing API key → error naming the exact env var required
- [ ] API batch embedding splits into groups of 512
- [ ] `pytest tests/ -x -v` passes with both local and API backends (API tests mocked)
