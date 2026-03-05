# Vision — codesight

## What It Is

codesight is an AI-powered document search engine that you deploy for clients as a consulting tool. Point it at a folder of documents — PDFs, Word docs, presentations, code, markdown — and it indexes everything into a hybrid search index. Users ask questions in plain English and get precise answers with source citations.

## The Core Business

**Option B: Consulting tool — your secret weapon.**

You walk into a company with a laptop. "Give me the folder of documents you need answers from." Index it, show them the web chat, they're amazed. Deliverable: a deployed instance + training. You charge for the engagement, not per user.

You are not selling software. You are selling expertise + a fast way to make any document collection searchable with AI.

## The Problem

Companies sit on mountains of documents — contracts, proposals, policies, technical specs, compliance records — spread across folders, drives, and systems. Finding specific information means manually searching through files, reading dozens of pages, and hoping you didn't miss anything. Knowledge workers spend 20%+ of their time searching for information.

## The Solution

Point codesight at a folder. It indexes everything into a hybrid search index. Then ask questions in natural language. codesight retrieves the most relevant chunks from across all documents and uses an LLM to synthesize a precise answer with source citations.

**The ultimate stack:**
- **Search and indexing: 100% local.** Embedding model runs on the machine. No data leaves. Ever.
- **Answer synthesis: client's choice.** Their own Claude API key, their Azure OpenAI tenant, or a local LLM (Ollama). They pick the trust level.
- **Deployment: wherever they want.** Their Azure, their AWS, a VM, a laptop. Docker container runs anywhere.

## Key Differentiator

**Adaptive multi-strategy retrieval with verification loops.** Most competitors use a single retrieval strategy. CodeSight adapts per query:

1. **Semantic cache** checks first — 50-65% of queries answered instantly without touching retrieval or LLM
2. **Hybrid BM25 + vector + RRF** for all retrieval — catches what vector-only misses (exact numbers, dates, section references)
3. **Cross-encoder reranking** for precision — +17-22pp over hybrid alone
4. **JIT context** for volatile sources — code repos, active wikis stay fresh via webhooks
5. **Agentic decomposition** for multi-hop questions — breaks complex queries into parallel sub-queries
6. **Verification loops** after every answer — hallucination detection + source citations before the user sees anything

For scoped document collections (hundreds to thousands of documents), this adaptive approach matches or beats cloud search services — at zero ongoing search cost, with complete data privacy.

## Delivery Channels

1. **Web Chat UI** (Streamlit) — browser-based Q&A for non-technical users
2. **CLI** — developer-friendly command-line interface
3. **Teams Bot** (planned) — answer questions in Microsoft Teams, natural for M365 orgs
4. **Slack Bot** (planned) — for non-Microsoft shops
5. **Python API** — `CodeSight` class for programmatic integration

## Design Principles

1. **Read-only** — codesight never writes to the indexed folder. Zero risk of data corruption.
2. **Data stays local** — search and indexing run entirely on the machine. Only answer synthesis optionally calls an external API, and the client controls which one.
3. **Pluggable LLM** — Claude API, Azure OpenAI, OpenAI, or Ollama (local). Client picks based on their security requirements.
4. **Simple API** — four methods: `index()`, `search()`, `ask()`, `status()`. Any interface calls the same methods.
5. **Deploy anywhere** — Docker container runs on Azure, AWS, GCP, on-prem, or a laptop.

## Target User

- **Primary:** Mid-size companies (20-500 people) who need their document collections searchable with AI — delivered via consulting engagement
- **Secondary:** Consulting firms, legal teams, and auditors who need to quickly understand large document sets for specific projects
- **Tertiary:** Developers who want semantic search over codebases and technical documentation

## What CodeSight Is NOT

- **Not a replacement for Microsoft Copilot.** If they already have Copilot searching across their M365, let it. CodeSight is for scoped project work, specific document folders, or companies without Copilot.
- **Not a SaaS product (yet).** It's a consulting deliverable. The software is the tool; the value is the engagement.
- **Not cloud-dependent.** The core engine runs locally. Cloud is optional for the LLM answer synthesis layer.
