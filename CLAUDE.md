# codesight

Semantic code search MCP server — hybrid BM25 + vector + RRF retrieval for Claude Code.

## Commands

- Run: `python -m semantic_search_mcp`
- Test: `pytest tests/ -x -v`
- Lint: `ruff check src/ tests/`
- Install: `pip install -e ".[dev]"`
- MCP Inspector: `npx @modelcontextprotocol/inspector python -m semantic_search_mcp`

## IMPORTANT Rules

- **Read-only invariant** — the MCP server NEVER writes to indexed repositories. It only reads files to build the index. Violating this is the most critical bug possible.
- **Path traversal prevention** — all `repo_path` inputs must be validated against a whitelist or resolved to real paths before use. Never allow `../` escapes.
- **Content hash guard** — always check `sha256(chunk_content)[:16]` before re-embedding. Never embed unchanged content.
- **No full file exposure** — the `search` tool returns chunks with line ranges, never entire file contents.

## Context

- Architecture: @ARCHITECTURE.md
- Rules: @.claude/rules/
- Decisions: @docs/decisions/
- Env template: @.env.example

## Rule Imports

@import .claude/rules/delegation.md
