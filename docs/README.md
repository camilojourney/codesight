# docs — codesight

## Contents

| Path | Purpose |
|------|---------|
| [vision.md](vision.md) | Product vision, core business, design principles |
| [roadmap.md](roadmap.md) | Versioned feature roadmap (v0.1 through v1.0) |
| [research/](research/INDEX.md) | Research (Mode B): stack, architecture, market, security |
| [decisions/](decisions/) | Architecture Decision Records (ADRs) |
| [playbooks/](playbooks/) | Step-by-step operational guides |

## Research (Mode B)

| File | Scope | Cadence |
|------|-------|---------|
| [research/stack.md](research/stack.md) | Embedding models, LLM backends, vector DBs | 30d |
| [research/benchmarks.md](research/benchmarks.md) | Precision@K, latency, cost projections | 30d |
| [research/architecture.md](research/architecture.md) | RAG pipeline, retrieval patterns, deployment | 90d |
| [research/market.md](research/market.md) | Competitors, pricing, positioning | 60d |
| [research/security.md](research/security.md) | ACL, auth, compliance, data privacy | 60d |

## Playbooks

| Path | Purpose |
|------|---------|
| [playbooks/development.md](playbooks/development.md) | Dev setup, CLI commands, environment variables |
| [playbooks/ship-feature.md](playbooks/ship-feature.md) | Process for shipping new features |
| [playbooks/investigate-bug.md](playbooks/investigate-bug.md) | Bug investigation workflow |

## Rules

**Only these categories belong in `docs/`:** README.md, vision.md, roadmap.md, research/, decisions/, playbooks/.

For feature specifications: `specs/`
For agent instructions: `.claude/agents/`
For business/sales materials: `business/`
