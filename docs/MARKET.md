# Market — CodeSight

**Last updated:** 2026-02

---

## The Problem

AI coding assistants (Claude Code, Cursor, GitHub Copilot) need deep codebase understanding to give accurate answers. But their built-in search is either keyword-only (misses semantic intent) or limited to small context windows. Developers waste time manually pointing the AI to the right files or getting wrong answers because the AI can't find relevant code.

## Why Now

1. **MCP protocol adoption** — Anthropic's Model Context Protocol is becoming the standard for extending AI assistants. Claude Code, Cursor, and VS Code all support MCP servers.
2. **AI coding assistant explosion** — Claude Code, Cursor, GitHub Copilot, Windsurf, Cline — every developer will use an AI coding assistant by 2027.
3. **Codebase size is growing** — monorepos with 100K+ files are common. Simple grep doesn't scale for semantic queries.
4. **Local-first is winning** — developers don't want to send their code to a cloud service for indexing. Local embedding models are now fast enough.

## Category

Semantic code search MCP server — hybrid BM25 + vector retrieval for AI coding assistants.

## Target User

- **Primary:** Developers using Claude Code, Cursor, or any MCP-compatible AI assistant
- **Secondary:** Teams with large codebases (monorepos, microservices) needing better code navigation
- **Tertiary:** DevEx teams building internal tools on MCP

## The Wedge

A pip-installable MCP server that gives any Claude Code session semantic code search in one command:
```bash
claude mcp add codesight -- python -m semantic_search_mcp
```

No cloud account. No API key. No configuration. Just search.

## Competitive Landscape

| Tool | Approach | Weakness |
|------|----------|----------|
| **Sourcegraph** | Enterprise code search | $49/user/mo, cloud-hosted, complex setup |
| **GitHub Code Search** | Keyword + regex | No semantic understanding |
| **Greptile** | AI-powered code search API | Cloud-only, requires sending code to their servers |
| **Cursor's built-in** | @codebase semantic search | Bundled with Cursor, not portable |
| **Claude Code grep** | Regex-based (ripgrep) | No semantic search, keyword only |
| **Continue.dev** | Open-source AI coding assistant | Broader scope, search is not the focus |

### Positioning

```
        ↑ Semantic Quality (High)
        |
        |  Sourcegraph ●        Greptile ●
        |
        |              [CODESIGHT]
        |                  ●
        |
        |  GitHub Code Search ●
        |
        |              grep/ripgrep ●
        ↓ Semantic Quality (Low)
←───────────────────────────────────────→
Cloud-hosted                  Local-first
```

**CodeSight is the only local-first semantic code search that works as an MCP server.**

## Market Size

| Segment | Size |
|---------|------|
| Developer tools market | $15B (2025), growing 20%+ CAGR |
| AI code assistants | $5B (2025), fastest-growing segment |
| Code search specifically | ~$500M |
| MCP ecosystem tools | Nascent — first-mover advantage |

## Business Model

### Phase 1 — Open Source / Free (Current)
- Build adoption and community
- Establish as the standard MCP code search tool
- No revenue — this is distribution building

### Phase 2 — Freemium
- **Free:** Single-repo, local embeddings, basic search
- **Pro ($9/mo):** Multi-repo, better embeddings (code-specific), watch mode, search history
- **Team ($29/user/mo):** Shared indexes, cross-repo search, enterprise embedding models

### Phase 3 — Enterprise
- **Enterprise ($99/user/mo):** Self-hosted, SSO, audit logs, custom connectors (Jira, Confluence)

## Growth Strategy

1. **Ship to MCP ecosystem** — get listed in Claude Code recommended tools
2. **GitHub stars → adoption** — open source credibility drives organic installs
3. **Blog content** — "How to add semantic search to Claude Code" tutorials
4. **Community plugins** — support more AI assistants (Cursor, Continue.dev, Cline)
5. **VS Code extension** — broader than MCP alone

## Moats

1. **MCP-native design** — built for the protocol, not retrofitted
2. **Local-first** — no code leaves the developer's machine
3. **Hybrid retrieval (BM25 + vector + RRF)** — better results than vector-only or keyword-only
4. **Zero configuration** — pip install + one command
5. **Language-aware chunking** — understands code structure in 10 languages

## Kill Criteria

- Claude Code ships built-in semantic search (eliminates the need)
- MCP protocol abandoned (eliminates the distribution channel)
- No organic installs after 3 months on GitHub
- Sourcegraph ships a free local tier
