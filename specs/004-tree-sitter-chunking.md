# Spec 004: AST-Based Code Chunking (tree-sitter)

**Status:** draft
**Phase:** v0.4
**Research deps:** research/architecture.md §2.2 (AST-Based Chunking — cAST evidence), research/benchmarks.md §1.2 (Config F — AST chunking in benchmark matrix), research/stack.md §1.3 (Embedding — voyage-code-3 for code files)
**Depends on:** Spec 001 (core search engine — chunk storage and retrieval pipeline)
**Blocks:** none
**Created:** 2026-02-24
**Updated:** 2026-03-04

## Problem

The current regex-based chunker splits code files on pattern matches at function and class boundaries. This approach has known failure modes that directly hurt retrieval quality:

- Regex cannot handle nested structures — a method inside a class inside a module is often split at the wrong boundary
- Decorators, multiline signatures, and context managers are separated from their function bodies
- Languages with unusual scope syntax (Rust `impl` blocks, Go receiver functions, Ruby `do..end`) require per-language regex patterns that are fragile and hard to maintain

When a chunk boundary splits a function in the middle, the embedding captures incomplete meaning. Search results show broken context, and the retrieval quality metric drops. cAST (AST-based chunking) achieves +4.3 Recall@5 on RepoEval vs regex chunking (research/architecture.md §2.2) [VERIFIED, Grade A — arXiv 2506.15655, EMNLP 2025, CMU + Augment Code].

The benchmark harness planned for v0.4 (benchmarks.md §1.2, Config F) [VERIFIED] explicitly tests AST-chunked retrieval. This feature must exist before those benchmarks can run.

## Goals

- Replace regex chunking with tree-sitter AST parsing for all 10 supported code languages (research/architecture.md §2.2) [VERIFIED]
- Chunk boundaries align exactly with AST node boundaries (function, class, method, struct, impl, module) — no mid-function splits
- Hierarchical context headers include the full scope path (`class Foo > method bar`) so embeddings capture structural context even when the method body lacks the relevant keywords
- Recall@5 improves by at least +4.3 points on a code search benchmark compared to regex chunking (research/architecture.md §2.2) [VERIFIED, Grade A]
- Graceful fallback to sliding window chunking for languages without a tree-sitter grammar — no crash, no empty results
- No change to the public `CodeSight` API or to the `Chunk` datatype — chunking is an internal implementation detail

## Non-Goals

- Full LSP or semantic analysis — type information, import graphs, and call graphs require a language server; AST node boundaries are sufficient for chunking
- Cross-file reference tracking — chunk-level search does not require knowing which functions call which
- Document file chunking — PDF, DOCX, and PPTX files use paragraph-based chunking (Spec 001); AST chunking applies only to code files
- Replacing the sliding window fallback — it remains the default for unrecognized languages and plain text files

## Solution

The chunker detects the file's language, checks whether a tree-sitter grammar is available for that language, and routes accordingly. For supported languages, it parses the file into an AST and walks the tree top-down, emitting chunks at scope node boundaries. For unsupported languages, the existing sliding window path runs unchanged.

```
File enters chunker:
    |
    ├── Code file? (extension check)
    |   ├── Yes: detect language
    |   |     ├── Grammar available? → AST chunking path
    |   |     └── No grammar → sliding window fallback (unchanged)
    |   └── No: document file → paragraph chunking (unchanged)
    |
AST chunking path:
    |
    ├── Parse source with tree-sitter → AST
    ├── Walk tree top-down, collect scope nodes
    |   (function, class, method, struct, impl, module — language-dependent)
    |
    ├── For each scope node:
    |   ├── Node text ≤ max_chars → emit as chunk
    |   ├── Node text > max_chars → recurse into child scope nodes
    |   └── Leaf scope still > max_chars → split by statement boundaries
    |
    └── Each chunk: prepend context header
          # File: src/auth/jwt.py
          # Scope: class JWTValidator > method validate_token
          # Lines: 45-82
```

The key advantage over regex: tree-sitter provides the full scope path at each node, not just the immediate ancestor. A method inside a class inside a module gets the header `module auth > class JWTValidator > method validate_token`. This hierarchical context is embedded alongside the code, improving retrieval for queries like "JWT validation" even when those words don't appear in the method body.

## Core Specifications

**SPEC-001: AST-based parsing for 10 supported languages**

| Field | Value |
|-------|-------|
| Description | Parse code files using tree-sitter grammars to obtain a concrete syntax tree, then walk the tree to identify scope node boundaries for chunking |
| Trigger | `chunk_file()` called on a file whose extension maps to one of the 10 supported languages |
| Input | Source text, file path, detected language, max chunk size in characters |
| Output | List of `Chunk` objects with content, file path, start line, end line, scope path |
| Validation | If the parse fails or produces only `ERROR` nodes, fall back to SPEC-005 (regex fallback) and log a warning |
| Auth Required | No |

Acceptance Criteria:
- [ ] All 10 languages (Python, JavaScript, TypeScript, Go, Rust, Java, Ruby, PHP, C, C++) produce chunks via AST parsing
- [ ] Chunk boundaries align exactly with AST scope node boundaries — no chunk ends mid-function
- [ ] The existing `Chunk` dataclass is reused without schema changes
- [ ] No change to LanceDB or SQLite FTS5 schema

**SPEC-002: Hierarchical scope-path context header**

| Field | Value |
|-------|-------|
| Description | Each chunk is prepended with a context header that shows the full ancestor scope path from the file root to the immediate scope node |
| Trigger | Chunk creation from any scope node during AST walk |
| Input | File path, list of ancestor scope node labels from root to the current node, start/end line numbers |
| Output | A text header of the form `# File: <path>\n# Scope: <scope1> > <scope2>\n# Lines: <start>-<end>` prepended to the chunk content before embedding |
| Validation | Scope path must include at least the immediate scope node label; root-level code with no enclosing scope uses `# Scope: module` |
| Auth Required | No |

Acceptance Criteria:
- [ ] A method inside a class produces a scope header with both `class Foo` and `method bar` in the path
- [ ] Top-level functions produce a scope header with just the function name
- [ ] Context headers are included in the text that is embedded (not stripped before embedding)
- [ ] Recall@5 on a code search benchmark improves by at least +4.3 points vs regex chunking (research/architecture.md §2.2) [VERIFIED, Grade A]

**SPEC-003: Recursive splitting for oversized nodes**

| Field | Value |
|-------|-------|
| Description | When a scope node's text exceeds `max_chars`, recurse into its child scope nodes rather than emitting an oversized chunk; if a leaf scope node still exceeds `max_chars`, split by statement boundaries within that node |
| Trigger | Scope node text length > `max_chars` during AST walk |
| Input | Current scope node, max_chars threshold, current scope path |
| Output | Multiple smaller chunks covering the node's content, each with an appropriate scope header |
| Validation | Recursion depth is bounded by `max_tree_depth`; beyond this depth, the remaining subtree is emitted as a single chunk even if it exceeds `max_chars` |
| Auth Required | No |

Acceptance Criteria:
- [ ] A class with 10 methods produces one chunk per method, not one oversized class chunk
- [ ] A single method exceeding `max_chars` is split by statement boundaries, not at an arbitrary character offset
- [ ] Recursion stops at `max_tree_depth=5` to prevent micro-chunks from pathologically nested code

**SPEC-004: Sliding window fallback for unsupported languages**

| Field | Value |
|-------|-------|
| Description | Files in languages without a tree-sitter grammar are chunked using the existing sliding window algorithm with overlap — no crash, no empty output |
| Trigger | `chunk_file()` called on a file whose language has no grammar in the grammar bundle |
| Input | Source text, file path, language identifier (unknown), configured window size and overlap |
| Output | Chunks produced by the sliding window algorithm, identical to pre-spec behavior |
| Validation | The fallback path is exercised for any extension not in the 10-language support matrix |
| Auth Required | No |

Acceptance Criteria:
- [ ] A `.lua` file (not in the support matrix) is chunked without error and returned as sliding window chunks
- [ ] The fallback produces the same output as the pre-spec regex/sliding window chunker for the same file
- [ ] No regression on existing test suite: `pytest tests/ -x -v` passes without changes to non-code-file tests

**SPEC-005: Parse error fallback**

| Field | Value |
|-------|-------|
| Description | If tree-sitter produces a tree where the root or top-level nodes are `ERROR` nodes (indicating severe syntax errors), fall back to the regex chunker for that file and log a warning |
| Trigger | AST parse produces `ERROR` nodes at a significant fraction of the tree |
| Input | Parsed AST with ERROR nodes, file path |
| Output | Chunks from the regex fallback path; a warning log entry identifying the file and error |
| Validation | The fallback threshold is: if > 20% of top-level child nodes are ERROR nodes, use regex fallback |
| Auth Required | No |

Acceptance Criteria:
- [ ] A syntactically invalid Python file produces chunks via the regex fallback, not an exception
- [ ] A warning is logged with the file path and indication that AST parsing failed
- [ ] Partially valid files (minor syntax errors) still produce AST chunks for the valid portions

## Edge Cases & Failure Modes

**EDGE-001: Syntax errors in source file**
- Scenario: A file has a syntax error that causes tree-sitter to emit ERROR nodes
- Expected behavior: Fall back to regex chunker for that file; log a warning
- Error message: `"AST parse failed for {file_path}: {error_node_count} ERROR nodes — falling back to regex chunking"`
- Recovery: Regex chunking runs automatically; the file is indexed with lower-quality chunks until the syntax error is fixed

**EDGE-002: Mixed language file (HTML with embedded JavaScript)**
- Scenario: An HTML file contains `<script>` blocks with JavaScript
- Expected behavior: The file is chunked as HTML (the outer language). Embedded `<script>` content is treated as text within the HTML chunk — tree-sitter-html is not in the support matrix
- Error message: none
- Recovery: Sliding window fallback for `.html` files handles this transparently

**EDGE-003: Code nested beyond max_tree_depth**
- Scenario: Code is nested more than 5 levels deep (e.g., deeply nested closures or lambdas)
- Expected behavior: Recursion stops at depth 5; the remaining subtree is emitted as a single chunk, even if it exceeds `max_chars` slightly
- Error message: none — handled silently
- Recovery: None needed; the oversized chunk is indexed and searchable, just at lower granularity

**EDGE-004: Empty file**
- Scenario: `chunk_file()` is called on a file with zero bytes or only whitespace
- Expected behavior: Returns an empty list — no chunks emitted
- Error message: none
- Recovery: Automatic — identical to current behavior for empty files

**EDGE-005: Single massive function exceeding max_chars with no sub-scopes**
- Scenario: A 5,000-character function contains no nested functions or classes — it is a leaf scope node larger than `max_chars`
- Expected behavior: Split by statement boundaries within the function body, using the function's scope header on each sub-chunk
- Error message: none
- Recovery: Automatic — each sub-chunk inherits the function's scope path

**EDGE-006: Binary file misidentified as code**
- Scenario: A binary file has a `.py` or `.js` extension and is passed to the AST chunker
- Expected behavior: tree-sitter parse fails immediately on non-UTF-8 input; the file is skipped via the parse-error fallback (SPEC-005), which in turn skips non-text content at the regex stage
- Error message: logged at debug level
- Recovery: File is excluded from the index; no chunks produced

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max chunk size | 1,500 characters | Consistent with existing chunker — maintains comparability across code and document chunks |
| Min chunk size | 100 characters | Prevents micro-chunks from small helper functions that add noise to the index |
| Overlap | 0 characters | AST boundaries are semantically clean — overlap is not needed, unlike sliding window where boundaries are arbitrary (research/architecture.md §2.2) [VERIFIED] |
| Max tree depth | 5 levels | Prevents pathological nesting from generating micro-chunks; matches cAST reference implementation |
| Parse error threshold | >20% top-level ERROR nodes | Allows partially-valid files to still use AST chunking for valid sections |

## Supported Languages

| Language | Scope Nodes |
|----------|-------------|
| Python | `function_definition`, `class_definition` |
| JavaScript | `function_declaration`, `class_declaration`, `arrow_function` |
| TypeScript | `function_declaration`, `class_declaration`, `interface_declaration` |
| Go | `function_declaration`, `method_declaration`, `type_declaration` |
| Rust | `function_item`, `impl_item`, `struct_item`, `enum_item` |
| Java | `method_declaration`, `class_declaration`, `interface_declaration` |
| Ruby | `method`, `class`, `module` |
| PHP | `function_definition`, `class_declaration`, `method_declaration` |
| C | `function_definition`, `struct_specifier` |
| C++ | `function_definition`, `class_specifier`, `namespace_definition` |

## Implementation Notes

### Dependencies

Two new packages are required:
- `tree-sitter>=0.22` — core parsing library (Python bindings)
- `tree-sitter-languages>=1.10` — pre-built grammar bundle for all 10 supported languages

These are added as required dependencies (not optional extras) since AST chunking is the default code chunking path. The bundle approach (`tree-sitter-languages`) avoids managing individual per-language grammar packages and handles version pinning centrally.

### Module Structure

A new `tree_sitter_chunker.py` module is added alongside the existing `chunker.py`. The entry point in `chunker.py` routes to the AST chunker when the language is in the support matrix and the grammar is available, then falls back to the regex path. The `Chunk` datatype is unchanged — only the `scope` field is populated with the full hierarchical path instead of just the immediate scope name.

### Benchmark Validation

The v0.4 benchmark harness (benchmarks.md §1.2, Config F) [VERIFIED] runs retrieval-only benchmarks with AST chunking enabled. The Recall@5 improvement of +4.3 points from the cAST paper (research/architecture.md §2.2) [VERIFIED, Grade A] is the target. Internal benchmark results are stored in `tests/benchmarks/results.db` for reproducibility.

## Alternatives Considered

### Alternative A: Language Server Protocol (LSP)

Trade-off: Full semantic understanding — types, imports, call graphs.
Rejected because: Requires a running language server per language (pyright, tsserver, gopls), adding a service dependency. AST node boundaries (function, class) are the right granularity for chunking without semantic analysis overhead.

### Alternative B: Improved regex patterns

Trade-off: No new dependencies; incremental improvement over current approach.
Rejected because: Regex fundamentally cannot handle nested structures or multi-line constructs reliably. Each language edge case requires a more complex pattern. tree-sitter handles all cases by parsing the actual grammar. The +4.3 Recall@5 gain (research/architecture.md §2.2) [VERIFIED, Grade A] justifies the dependency.

### Alternative C: Individual per-language grammar packages

Trade-off: More granular version control per language.
Rejected because: `tree-sitter-languages` bundles all 10 grammars with tested compatibility. Managing 10 separate packages increases dependency surface and risk of version conflicts with no practical benefit at this scale.

## Open Questions

- [ ] Should context headers show the full scope path (`class Foo > method bar`) or just the immediate scope? Full path is more informative but adds more tokens before embedding — measure embedding quality with both — @juan
- [ ] Is 1,500 characters still the right `max_chars` for AST-based chunks? AST boundaries produce naturally coherent units that may be better at larger sizes — benchmark with 2,000 chars — @juan
- [ ] Should `tree-sitter-languages` or individual grammar packages be the dependency? Bundle is simpler; individual packages allow per-language version pinning — @juan

## Acceptance Criteria

- [ ] tree-sitter used for all 10 supported languages: Python, JavaScript, TypeScript, Go, Rust, Java, Ruby, PHP, C, C++
- [ ] Chunk boundaries align exactly with AST node boundaries — no mid-function splits on any test file
- [ ] Hierarchical context header includes full scope path (e.g., `class Foo > method bar`) for nested scopes
- [ ] Recall@5 improves by at least +4.3 points vs regex chunking on a code search benchmark (research/architecture.md §2.2) [VERIFIED, Grade A]
- [ ] Fallback to sliding window for unsupported languages — no crash, no empty results
- [ ] Syntax errors in source → graceful fallback to regex, warning logged with file path
- [ ] Existing `Chunk` dataclass reused — no schema changes to LanceDB or SQLite
- [ ] Document files (PDF, DOCX, PPTX) unaffected — paragraph chunking unchanged
- [ ] `pytest tests/ -x -v` passes with no regressions on the existing test suite
- [ ] Benchmark Config F (benchmarks.md §1.2) [VERIFIED] runs successfully against a code repository corpus
