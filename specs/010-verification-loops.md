# Spec 010: Verification Loops

**Status:** draft
**Phase:** v0.4
**Research deps:** research/stack.md §5.4 (Verification Loop — HHEM, Claude Citations, confidence gate), research/architecture.md §5.2 (Recommended Architecture — verification pipeline), research/security.md §4 (Guardrails — multi-layer defense), research/benchmarks.md §1.2 (Hallucination Rate target <10%)
**Depends on:** Spec 001 (core search engine — `ask()` pipeline), Spec 007 (reranking improves context quality for verification)
**Blocks:** none
**Created:** 2026-03-04
**Updated:** 2026-03-04

## Problem

When `ask()` generates an answer from retrieved chunks, there is no verification that the answer is actually grounded in the source material. The LLM can hallucinate — synthesizing plausible-sounding statements that are not supported by the retrieved context. In consulting, a hallucinated answer about a client's contract terms or compliance requirements is worse than no answer at all.

Current state: the answer goes from LLM directly to the user with no quality check. The user has no way to know whether the answer is grounded or fabricated. The [Source N] citations in the answer text are cosmetic — they reference chunks that were in the context, but the LLM may ignore or misrepresent those chunks.

Research shows a multi-layer verification approach reduces hallucination from a baseline to under 10% (research/security.md §4.2 — 73.2% → 8.7% attack success with 3-layer defense) [VERIFIED, Grade B]. The verification loop adds grounding checks, source attribution, and a confidence gate that routes low-confidence answers to a retry or "I don't know" path.

## Goals

- HHEM hallucination detection: score each answer 0-1 for grounding in retrieved context (research/stack.md §5.4 — Vectara HHEM, <600MB, CPU, ~1.5s) [VERIFIED, Grade A]
- Claude Citations API integration: every factual claim in the answer cites a specific source chunk (research/stack.md §5.4 — free, no additional tokens) [VERIFIED, Grade A]
- Confidence gate: low-grounding answers trigger query rewrite + retry or "I don't know" response (research/stack.md §5.4) [VERIFIED]
- `Answer` object includes a `grounding_score` (0.0-1.0) for downstream use (caching, logging, client-facing confidence)
- Hallucination Rate < 10% on the benchmark question bank (research/benchmarks.md §1.2) [VERIFIED]

## Non-Goals

- NeMo Guardrails integration — planned for v1.0 (research/security.md §4.3) [VERIFIED, Grade A]; requires per-chunk retrieval rails that are overkill for v0.4
- Real-time user feedback loop — users flagging bad answers is a v1.0 feature
- Prompt injection defense — handled separately by input sanitization (research/security.md §4.2)
- Semantic cache validation (SAFE-CACHE) — depends on semantic cache (v0.5) (research/security.md §4.2) [VERIFIED, Grade B]
- Fine-tuning HHEM on domain-specific data — pre-trained model is sufficient for general consulting documents

## Solution

The verification loop is inserted between LLM answer generation and response return. It runs three checks in sequence: HHEM grounding, Claude Citations extraction, and a confidence gate. If the confidence gate fails, the system rewrites the query and retries (up to 2 times) or returns a transparent "I don't know" response with the raw retrieved chunks.

```
ask(question)
    │
    ▼
search(question) → top 5 chunks                [ALWAYS LOCAL]
    │
    ▼
LLM generates answer (with citations if Claude)
    │
    ▼
┌─── Verification Loop ────────────────────────┐
│                                               │
│  1. HHEM grounding check                      │
│     Score 0-1: is answer supported by chunks? │
│     (~1.5s CPU, <600MB model)                 │
│                                               │
│  2. Claude Citations extraction               │
│     Parse cited_text from API response        │
│     (0ms overhead — part of generation)       │
│                                               │
│  3. Confidence gate                           │
│     IF hhem_score ≥ 0.7 AND citations exist:  │
│       → return answer (high confidence)       │
│     IF hhem_score < 0.5 OR no citations:      │
│       → rewrite query, retry (max 2)          │
│       → if still fails: "I don't know" +      │
│         raw chunks                            │
│     IF 0.5 ≤ hhem_score < 0.7:               │
│       → return answer with low-confidence     │
│         warning                               │
│                                               │
└───────────────────────────────────────────────┘
    │
    ▼
Answer(text, sources, model, grounding_score, citations)
```

The verification loop is enabled by default when using the Claude backend (Citations API is backend-specific). For non-Claude backends, HHEM grounding still runs but citations are unavailable — the confidence gate adapts its thresholds accordingly.

## Core Specifications

**SPEC-001: HHEM hallucination detection**

| Field | Value |
|-------|-------|
| Description | Score each `ask()` answer for grounding against the retrieved context using the Vectara HHEM model. The score ranges from 0 (completely hallucinated) to 1 (fully grounded). |
| Trigger | Every `ask()` call when verification is enabled (`CODESIGHT_VERIFY=true`, default: true) |
| Input | Generated answer text + list of retrieved context chunks |
| Output | `grounding_score` float (0.0 to 1.0) added to the `Answer` object |
| Validation | Model loaded lazily on first use; cached for process lifetime. If model fails to load, verification is skipped with a warning. |
| Auth Required | No (model is local, open source) |

Acceptance Criteria:
- [ ] HHEM model (`vectara/hallucination_evaluation_model`) loaded on first `ask()` call (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] Model size < 600MB on disk (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] Grounding score computed in ~1.5s on CPU (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] `Answer.grounding_score` is populated on every verified `ask()` response
- [ ] Model failure → verification skipped, `grounding_score=None`, warning logged

**SPEC-002: Claude Citations API integration**

| Field | Value |
|-------|-------|
| Description | When using the Claude backend, extract `cited_text` references from the API response to identify which specific passages the LLM used to support each claim in the answer |
| Trigger | Every `ask()` call using the Claude backend |
| Input | Claude API response with citations enabled |
| Output | List of `Citation` objects (source chunk reference + cited text excerpt) added to the `Answer` object |
| Validation | Citations API is free — `cited_text` is not counted as output tokens (research/stack.md §5.4) [VERIFIED, Grade A]. Non-Claude backends skip this step — `Answer.citations` is empty. |
| Auth Required | Yes (Anthropic API key for Claude backend) |

Acceptance Criteria:
- [ ] Claude API called with citations enabled (parameter in the request)
- [ ] `Answer.citations` contains a list of `{chunk_id, cited_text, claim}` references
- [ ] Citations are free — no additional token cost (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] Non-Claude backends: `Answer.citations` is an empty list, not an error
- [ ] At least one citation present for factual answers (none expected for "I don't know" responses)

**SPEC-003: Confidence gate logic**

| Field | Value |
|-------|-------|
| Description | A decision gate that evaluates the grounding score and citation presence to determine whether to return the answer, retry with a rewritten query, or return a transparent "I don't know" |
| Trigger | After HHEM scoring and citation extraction complete |
| Input | `grounding_score`, `citations` list, retry count |
| Output | Decision: `pass` (return answer), `retry` (rewrite query), `refuse` (return "I don't know" + raw chunks) |
| Validation | Thresholds configurable via env vars; retry limit is 2 attempts total (research/stack.md §5.4) [VERIFIED] |
| Auth Required | No |

Acceptance Criteria:
- [ ] `grounding_score ≥ 0.7` AND citations present → answer returned as high confidence (research/stack.md §0.4 — confidence gate >0.7) [VERIFIED, Grade B]
- [ ] `grounding_score < 0.5` OR no citations for factual answer → trigger query rewrite + retry (research/stack.md §5.4) [VERIFIED]
- [ ] `0.5 ≤ grounding_score < 0.7` → answer returned with low-confidence warning appended
- [ ] Maximum 2 retry attempts before returning "I don't know" (research/stack.md §5.4) [VERIFIED]
- [ ] "I don't know" response includes the raw retrieved chunks so the user can read sources directly

**SPEC-004: Query rewrite on retry**

| Field | Value |
|-------|-------|
| Description | When the confidence gate triggers a retry, the original query is rewritten to be more specific or to target different aspects of the question, then retrieval and answer generation run again |
| Trigger | Confidence gate returns `retry` decision |
| Input | Original query, retrieved chunks that produced a low-confidence answer |
| Output | Rewritten query string used for the next retrieval + answer attempt |
| Validation | Rewrite uses the active LLM backend (same backend that generated the answer); rewrite prompt instructs the LLM to make the query more specific based on what was retrieved |
| Auth Required | Yes (LLM backend) |

Acceptance Criteria:
- [ ] Rewritten query string differs from the original query string
- [ ] The rewrite is a single LLM call with a short prompt (not a full `ask()` pipeline)
- [ ] Rewrite latency ≤ 500ms per retry

**SPEC-005: Answer object extension**

| Field | Value |
|-------|-------|
| Description | The `Answer` dataclass is extended with verification fields: `grounding_score`, `citations`, `confidence_level`, `retries` |
| Trigger | Every `ask()` call |
| Input | Verification pipeline results |
| Output | Extended `Answer` object with new fields |
| Validation | New fields are optional — existing code that only reads `text`, `sources`, `model` is unaffected |
| Auth Required | No |

Acceptance Criteria:
- [ ] `Answer.grounding_score`: float 0.0-1.0 or None (if verification disabled/failed)
- [ ] `Answer.citations`: list of Citation objects (empty if non-Claude backend)
- [ ] `Answer.confidence_level`: enum — `high`, `medium`, `low`, `refused`
- [ ] `Answer.retries`: int — number of retry attempts (0 if first attempt succeeded)
- [ ] Existing code reading `Answer.text`, `Answer.sources`, `Answer.model` works without modification — new fields have defaults

**SPEC-006: Verification toggle**

| Field | Value |
|-------|-------|
| Description | `CODESIGHT_VERIFY` env var enables or disables the verification loop globally |
| Trigger | Application startup or first `ask()` call |
| Input | `CODESIGHT_VERIFY` — `true` (default) or `false` |
| Output | Verification loop active or bypassed |
| Validation | When disabled, `grounding_score` is None, `citations` is empty, `confidence_level` is `high` (no check performed) |
| Auth Required | No |

Acceptance Criteria:
- [ ] `CODESIGHT_VERIFY=true` (default) enables the full verification loop
- [ ] `CODESIGHT_VERIFY=false` skips verification entirely — zero latency overhead
- [ ] Verification disabled → `Answer.grounding_score=None`, `Answer.confidence_level="high"`
- [ ] `search()` is never affected by verification settings (search is always local, always unverified)

## Edge Cases & Failure Modes

**EDGE-001: HHEM model fails to load**
- Scenario: The HHEM model download fails or the model file is corrupted
- Expected behavior: Verification degrades gracefully — HHEM scoring is skipped, confidence gate uses citations-only mode (if Claude backend) or is bypassed entirely
- Error message: `"WARNING: HHEM model failed to load — grounding verification disabled. Install with: pip install codesight[verify]"`
- Recovery: Re-download the model; `pip install codesight[verify]` ensures dependencies

**EDGE-002: Non-Claude backend (no citations)**
- Scenario: `CODESIGHT_LLM_BACKEND=ollama` — Citations API is Claude-specific
- Expected behavior: HHEM grounding still runs. Confidence gate uses HHEM score only — thresholds adjusted (high confidence at ≥0.8 instead of ≥0.7 to compensate for missing citation signal)
- Error message: none — automatic adaptation
- Recovery: N/A

**EDGE-003: All retries exhausted**
- Scenario: Both retry attempts produce low-confidence answers
- Expected behavior: Return "I couldn't find a confident answer" text + raw retrieved chunks as sources. `confidence_level="refused"`, `retries=2`
- Error message: `Answer.text = "I couldn't find a confident answer to your question. Here are the most relevant sources I found — you may find the answer by reading them directly."`
- Recovery: User reads the raw chunks; or reformulates their question manually

**EDGE-004: Very short answer**
- Scenario: LLM returns a 1-2 word answer (e.g., "Yes" or "42")
- Expected behavior: HHEM may produce unreliable scores on very short text. If answer is < 20 characters, skip HHEM scoring and use citations-only for confidence
- Error message: none — handled silently
- Recovery: Automatic

**EDGE-005: Verification latency exceeds budget**
- Scenario: HHEM scoring takes >5s (slow CPU, large answer)
- Expected behavior: Timeout after 5 seconds; return the answer without a grounding score rather than blocking the user
- Error message: logged — `"HHEM scoring timed out after 5s — returning answer without grounding verification"`
- Recovery: Answer is returned with `grounding_score=None`; subsequent calls may be faster if the system warms up

**EDGE-006: Empty retrieved context**
- Scenario: `search()` returns no chunks but `ask()` is still called (edge case in the pipeline)
- Expected behavior: Skip verification entirely — there's nothing to ground against. Return the LLM's response (which should say "no relevant documents found") with `grounding_score=None`, `confidence_level="low"`
- Error message: none
- Recovery: Automatic

**EDGE-007: Query rewrite LLM call fails**
- Scenario: The LLM call to rewrite the query returns an error or empty string
- Expected behavior: Treat as a failed retry — decrement retry counter, proceed to next retry with the original query, or return "I don't know" if retries exhausted
- Error message: logged — `"Query rewrite failed — using original query for retry"`
- Recovery: Automatic — falls through to the retry/refuse logic

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Verification enabled (default) | `true` | On by default — hallucination prevention is critical for consulting |
| HHEM model | `vectara/hallucination_evaluation_model` | <600MB, CPU-compatible, 0-1 grounding score (research/stack.md §5.4) [VERIFIED, Grade A] |
| High confidence threshold | ≥ 0.7 (Claude), ≥ 0.8 (other backends) | research/stack.md §0.4 — confidence gate >0.7 for cache gating [VERIFIED, Grade B]; higher for non-Claude to compensate for missing citations |
| Low confidence threshold | < 0.5 | Triggers retry — answer is likely hallucinated (research/stack.md §5.4) [VERIFIED] |
| Max retries | 2 | Prevents infinite loops; 3 total LLM calls maximum per question (research/stack.md §5.4) [VERIFIED] |
| HHEM timeout | 5 seconds | Prevents blocking on slow hardware; ~1.5s expected (research/stack.md §5.4) [VERIFIED, Grade A] |
| HHEM short-text threshold | 20 characters | Below this, HHEM scores are unreliable — skip to citations-only |

## Implementation Notes

### Dependencies

One new optional package:
- `sentence-transformers>=3.0` — already installed for cross-encoder reranking (Spec 007); HHEM model uses the same library

The HHEM model (`vectara/hallucination_evaluation_model`) is downloaded on first use via HuggingFace Hub, similar to how the reranker model is handled in Spec 007. It's cached in the sentence-transformers cache directory.

### Module Structure

Verification logic is added to the existing `llm.py` or a new `verify.py` module:
- `verify.py` — HHEM scoring, citation extraction, confidence gate logic, query rewrite
- `Answer` dataclass in `models.py` extended with `grounding_score`, `citations`, `confidence_level`, `retries`

### Claude Citations API Usage

Citations are enabled by passing the citations parameter in the Claude API request. The response includes `cited_text` fields that reference specific passages from the input context. This is parsed by the `ClaudeBackend` adapter and passed to the verification module.

### Non-Claude Backend Adaptation

For OpenAI, Azure, and Ollama backends, citations are not available at the API level. The confidence gate operates on HHEM score alone, with a higher threshold (0.8 vs 0.7) to compensate. This is documented in the configuration so users understand the quality trade-off.

## Alternatives Considered

### Alternative A: Skip HHEM, use Claude Citations only

Trade-off: Zero additional latency; Claude Citations are free.
Rejected because: Citations only show what was referenced, not whether the answer accurately represents the source. A hallucinated answer can still cite the correct chunk — the citation proves the LLM saw the chunk, not that it used it correctly. HHEM checks semantic consistency between answer and source.

### Alternative B: Use DeepEval hallucination metric in real-time

Trade-off: More sophisticated hallucination detection; already planned as a dependency for Spec 009.
Rejected because: DeepEval's hallucination metric requires an LLM call for evaluation — it would double the LLM cost per query. HHEM is a local model (~1.5s CPU) with no additional API cost.

### Alternative C: Always return answers, flag low confidence in UI

Trade-off: Simpler — never refuse to answer; let the user decide.
Rejected because: In consulting, a confidently-presented wrong answer is a liability risk. The "I don't know" path is safer for high-stakes document Q&A. Users can always read the raw chunks if the system refuses.

### Alternative D: NeMo Guardrails for per-chunk validation

Trade-off: NVIDIA's Colang-based programmable guardrails validate each retrieved chunk before it enters LLM context (research/security.md §4.3) [VERIFIED, Grade A].
Rejected for v0.4: Requires learning the Colang language and adds significant complexity. HHEM + Citations is sufficient for v0.4. NeMo Guardrails is planned for v1.0 when enterprise-grade guardrails are needed.

## Open Questions

- [ ] Should the confidence gate thresholds be tuned per-client (e.g., legal documents need higher threshold than technical docs)? — @juan
- [ ] Should "I don't know" responses be tracked separately in analytics to identify gaps in the document corpus? — @juan
- [ ] Is the HHEM model accurate enough for code-related questions, or does it need a code-specific grounding model? — @juan
- [ ] Should verification be async (return answer immediately, verify in background, update if problematic)? — @juan

## Acceptance Criteria

- [ ] HHEM model scores each `ask()` answer with a grounding score (0.0-1.0) (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] HHEM latency ≤ 1.5s on CPU for typical answers (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] Claude Citations API extracts source references from answers at zero additional cost (research/stack.md §5.4) [VERIFIED, Grade A]
- [ ] Confidence gate: score ≥0.7 + citations → high confidence; <0.5 or no citations → retry (research/stack.md §5.4) [VERIFIED]
- [ ] Maximum 2 retries before returning "I don't know" + raw chunks (research/stack.md §5.4) [VERIFIED]
- [ ] `Answer.grounding_score`, `Answer.citations`, `Answer.confidence_level` fields populated
- [ ] Non-Claude backends: HHEM still runs, citations empty, thresholds adjusted
- [ ] `CODESIGHT_VERIFY=false` disables verification — zero overhead, identical to pre-spec behavior
- [ ] Hallucination Rate < 10% on the benchmark question bank (research/benchmarks.md §1.2 — target) [VERIFIED]
- [ ] Answers shorter than 20 characters skip HHEM scoring and use citations-only for confidence
- [ ] `search()` is unaffected — verification applies only to `ask()`
- [ ] `pytest tests/ -x -v` passes with verification both enabled and disabled
