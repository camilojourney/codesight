# Spec 006: Pluggable LLM Backend

**Status:** done
**Phase:** v0.3
**Research deps:** research/stack.md §2 (LLM Backends), research/architecture.md §5 (Recommended Architecture)
**Depends on:** Spec 001 (core search engine)
**Blocks:** Spec 008 (Docker deployment — backend configured per container)
**Created:** 2026-02-28
**Updated:** 2026-03-04

## Problem

`ask()` was hardcoded to the Anthropic Claude API. In consulting engagements, different clients have different security and vendor requirements:

- "We can't send data outside our Azure tenant" → needs Azure OpenAI
- "No data can leave our network, period" → needs local LLM via Ollama
- "We already have an OpenAI enterprise contract" → needs OpenAI API
- "We want the best answers possible" → Claude API is fine

The consultant must configure the LLM backend per client without changing code. The web chat UI and CLI must work identically regardless of which backend is selected.

## Goals

- Support 4 backends: Claude API, Azure OpenAI, OpenAI, Ollama — selected by a single env var (research/stack.md §2.2) [VERIFIED, Grade A]
- `search()` remains 100% local — no LLM backend needed, no data leaves (research/architecture.md §5.2) [VERIFIED]
- Same system prompt across all backends — same answer format and quality expectations
- `Answer.model` reports which backend + model was used for observability
- Clear errors when credentials are missing or backends are unreachable

## Non-Goals

- Supporting every LLM provider (Gemini, Mistral, Cohere, etc.) — add later by request
- Streaming responses — separate improvement, works with any backend
- Per-call model override — backend and model are config-level choices
- LLM quality benchmarking across backends — client chooses based on security, not quality comparison

## Solution

A single env var `CODESIGHT_LLM_BACKEND` selects the adapter. Each adapter implements the same `LLMBackend` protocol: receive `(system_prompt, user_prompt)` → return `str`. The `ask()` method calls the active adapter; `search()` never touches the adapter.

```
ask(question)
    │
    ▼
search(question) → top 5 chunks              [ALWAYS LOCAL]
    │
    ▼
Format: system prompt + ranked chunks + question    [SAME FOR ALL BACKENDS]
    │
    ▼
Active LLMBackend adapter                           [CLIENT'S CHOICE]
    ├── claude  → Anthropic API
    ├── azure   → Azure OpenAI (client's tenant)
    ├── openai  → OpenAI API
    └── ollama  → localhost:11434 (zero network)
    │
    ▼
Answer(text, sources, model)
```

Configuration is purely via environment variables — no code changes required to switch backends per engagement.

## Core Specifications

**SPEC-001: Backend selection**

| Field | Value |
|-------|-------|
| Description | `CODESIGHT_LLM_BACKEND` env var selects the active adapter at startup |
| Trigger | Application startup or first `ask()` call |
| Input | `CODESIGHT_LLM_BACKEND` value: `claude` | `azure` | `openai` | `ollama` |
| Output | Active `LLMBackend` adapter instance; `ValueError` on unknown value |
| Validation | Case-sensitive match against 4 known values |
| Auth Required | No (selection); Yes (credentials for the chosen backend) |

Acceptance Criteria:
- [ ] `CODESIGHT_LLM_BACKEND=claude` activates Anthropic adapter (default when unset)
- [ ] `CODESIGHT_LLM_BACKEND=azure` activates Azure OpenAI adapter
- [ ] `CODESIGHT_LLM_BACKEND=openai` activates OpenAI adapter
- [ ] `CODESIGHT_LLM_BACKEND=ollama` activates Ollama adapter
- [ ] Any other value raises `ValueError` listing the 4 valid options

**SPEC-002: search() is always local**

| Field | Value |
|-------|-------|
| Description | `search()` returns ranked chunks without ever calling any LLM backend |
| Trigger | Any `search()` call |
| Input | Query string |
| Output | `list[SearchResult]` from local BM25 + vector + RRF pipeline |
| Validation | No LLM env vars required |
| Auth Required | No |

Acceptance Criteria:
- [ ] `search()` succeeds with no `CODESIGHT_LLM_BACKEND` set and no API keys present
- [ ] `search()` produces identical results regardless of which LLM backend is configured
- [ ] No network calls are made during `search()`

**SPEC-003: Shared system prompt**

| Field | Value |
|-------|-------|
| Description | All backends receive the same system prompt — answer format and quality expectations are uniform |
| Trigger | Every `ask()` call |
| Input | `SYSTEM_PROMPT` constant + ranked chunks as context + user question |
| Output | Same structured answer format (with [Source N] citations) regardless of backend |
| Validation | System prompt is a module-level constant, not per-backend |
| Auth Required | No |

Acceptance Criteria:
- [ ] `SYSTEM_PROMPT` is defined once in `llm.py` and passed identically to all 4 adapters
- [ ] All backends produce answers with [Source N] citation format
- [ ] Changing backend does not change the prompt sent to the LLM

**SPEC-004: Answer model attribution**

| Field | Value |
|-------|-------|
| Description | `Answer.model` reports which backend and model name were used to generate the answer |
| Trigger | Every successful `ask()` call |
| Input | Active backend name + model name used |
| Output | `Answer.model` field in format `"<backend>:<model_name>"` e.g. `"claude:claude-sonnet-4-6"` |
| Validation | Populated by adapter before returning; never None on success |
| Auth Required | No |

Acceptance Criteria:
- [ ] `Answer.model` is set on every successful `ask()` response
- [ ] Format matches `"<backend>:<model>"` e.g. `"claude:claude-sonnet-4-6"`, `"ollama:llama3.1"`
- [ ] `Answer.model` reflects the actual model used, not just the configured backend

**SPEC-005: Credential validation**

| Field | Value |
|-------|-------|
| Description | Missing or invalid credentials produce a clear error naming the exact env var needed |
| Trigger | `ask()` call when credentials are absent or rejected |
| Input | Active backend; environment variables |
| Output | `ValueError` or `RuntimeError` with exact env var name in message |
| Validation | Credentials checked before first network call |
| Auth Required | Yes (backend-dependent) |

Acceptance Criteria:
- [ ] `claude` backend missing `ANTHROPIC_API_KEY` → error names `ANTHROPIC_API_KEY`
- [ ] `azure` backend missing any of `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` → error names the specific missing var
- [ ] `openai` backend missing `OPENAI_API_KEY` → error names `OPENAI_API_KEY`
- [ ] `ollama` backend missing server → error gives `ollama serve` command (not a credential error)

## Edge Cases & Failure Modes

**EDGE-001: Ollama server not running**
- Scenario: `CODESIGHT_LLM_BACKEND=ollama` but no Ollama process is listening at the configured URL
- Expected behavior: Connection refused on first `ask()` call; clear error with startup command
- Error message: `"Ollama server not found at localhost:11434. Start it with: ollama serve"`
- Recovery: User runs `ollama serve` in a terminal; retry `ask()`

**EDGE-002: Ollama model not downloaded**
- Scenario: Ollama is running but the configured model (e.g., `llama3.1`) is not present
- Expected behavior: Ollama returns 404-equivalent; surface with pull command
- Error message: `"Model 'llama3.1' not found in Ollama. Download it with: ollama pull llama3.1"`
- Recovery: User runs `ollama pull <model>`; retry

**EDGE-003: Azure deployment name mismatch**
- Scenario: `AZURE_OPENAI_DEPLOYMENT` is set but the deployment doesn't exist in the client's tenant
- Expected behavior: Azure API returns 404; surface error with context about checking the deployment name
- Error message: `"Azure OpenAI deployment 'gpt-4o' not found. Verify AZURE_OPENAI_DEPLOYMENT matches an active deployment in your Azure tenant."`
- Recovery: User corrects `AZURE_OPENAI_DEPLOYMENT` to match actual Azure deployment

**EDGE-004: API rate limit**
- Scenario: Cloud backend (Claude, Azure, OpenAI) returns 429
- Expected behavior: Retry once after 2-second delay; raise if still rate-limited
- Error message: `"LLM backend rate limited (claude). Retry after a brief pause or reduce concurrent usage."`
- Recovery: Wait and retry; for sustained load, reduce query volume or upgrade tier

**EDGE-005: Network timeout**
- Scenario: LLM API call exceeds 30-second timeout (slow network, overloaded server)
- Expected behavior: Raise with timeout message and local fallback suggestion
- Error message: `"LLM request timed out after 30s. Check network connectivity or switch to CODESIGHT_LLM_BACKEND=ollama for local inference."`
- Recovery: Switch to Ollama or retry on better network

**EDGE-006: ask() with no backend configured**
- Scenario: No `CODESIGHT_LLM_BACKEND` set; default is `claude`; no `ANTHROPIC_API_KEY` set
- Expected behavior: `search()` works fine (local only); `ask()` fails with credential error on first call
- Error message: `"ANTHROPIC_API_KEY is required for the claude backend. Set it in your environment or switch to CODESIGHT_LLM_BACKEND=ollama for local-only inference."`
- Recovery: Set API key or switch to Ollama

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Default backend | `claude` | Best answer quality, existing implementation (research/stack.md §2.2) [VERIFIED, Grade A] |
| Claude model | `claude-sonnet-4-6` | Best quality/cost for RAG synthesis at $3/$15 per MTok (research/stack.md §2.2) [VERIFIED, Grade A] |
| Ollama default model | `llama3.1` | 25-40 tok/s on 16GB Mac Apple Silicon (research/stack.md §2.3) [VERIFIED, Grade B] |
| Request timeout | 30 seconds | Prevents hanging on slow backends; Ollama may need a longer value for large models |
| Max retries | 1 (cloud), 0 (Ollama) | One retry for transient cloud API errors; Ollama errors are typically deterministic |

## Implementation Notes

`llm.py` defines the `LLMBackend` protocol with a single `generate(system_prompt, user_prompt) → str` method and four adapter implementations: `ClaudeBackend`, `AzureOpenAIBackend`, `OpenAIBackend`, `OllamaBackend`. A factory function `get_backend(config)` dispatches based on `config.llm_backend`.

Dependencies: `anthropic>=0.40` (already installed); `openai>=1.0` shared by Azure and OpenAI adapters (optional install via `codesight[azure]` or `codesight[openai]`); Ollama uses `httpx` which is already available via the `anthropic` transitive dependency.

## Alternatives Considered

### Alternative A: LiteLLM wrapper library

Trade-off: Abstracts 100+ providers behind one API, saves implementation time.
Rejected because: Heavy transitive dependency footprint. We need exactly 4 backends. Each adapter is ~30-50 lines of straightforward code.

### Alternative B: LangChain

Trade-off: Massive ecosystem, many integrations.
Rejected because: We need `send_prompt() → string`. LangChain's abstraction layers are extreme overkill for this interface.

### Alternative C: Only Claude + Ollama

Trade-off: Fewer backends to maintain.
Rejected because: Azure OpenAI is critical for enterprise clients already on Azure. OpenAI is trivial since it uses the same `openai` package as Azure.

## Open Questions

- [ ] Should Ollama timeout be longer than cloud API timeout? Local inference on CPU is slower. — @juan
- [ ] Should we validate Azure endpoint URL format on startup to catch misconfiguration early? — @juan

## Acceptance Criteria

- [ ] `CODESIGHT_LLM_BACKEND=claude` works with `ANTHROPIC_API_KEY` (existing behavior preserved)
- [ ] `CODESIGHT_LLM_BACKEND=azure` works with Azure OpenAI env vars
- [ ] `CODESIGHT_LLM_BACKEND=openai` works with `OPENAI_API_KEY`
- [ ] `CODESIGHT_LLM_BACKEND=ollama` works with local Ollama server
- [ ] Invalid backend name raises `ValueError` listing valid options
- [ ] Missing credentials produce error naming the exact env var required
- [ ] `search()` works with no LLM backend configured (100% local, no API keys)
- [ ] `Answer.model` reports backend + model used (e.g., `"claude:claude-sonnet-4-6"`)
- [ ] Same `SYSTEM_PROMPT` constant used across all 4 backends
- [ ] Web chat UI works identically with any backend
- [ ] `pytest tests/ -x -v` passes (cloud API tests mocked, Ollama test skipped if server absent)
