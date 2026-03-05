# Pitch — Read Before Every Client Meeting

## The 30-Second Pitch

"I make your company's documents searchable with AI. Point me at a folder — contracts, policies, specs — and your team can ask questions in plain English and get answers with page-level citations. Search runs entirely on your machine. No data leaves your network. Working system in days, not months."

---

## Before the Meeting

- [ ] Get 10-20 sample documents from the client (or prepare realistic examples)
- [ ] Index them: `python -m codesight index /path/to/docs`
- [ ] Test 5+ questions to make sure answers are good
- [ ] Launch demo: `python -m codesight demo`
- [ ] Calculate ROI: team size x searches/day x 15 min x hourly rate
- [ ] Have one-pager printed or PDF ready
- [ ] Know their stack (M365? Google? Confluence?)

## Numbers to Know

| Metric | Number |
|--------|--------|
| Time workers spend searching | 20%+ of work week (McKinsey) |
| Average search time per query | 15-30 minutes |
| CodeSight search time | < 5 seconds |
| CodeSight monthly cost (50 users) | $50-200 (API only) |
| Copilot monthly cost (50 users) | $1,500 |
| Glean monthly cost (50 users) | $2,250+ |
| Index speed (500 docs) | ~30 seconds |
| **Pilot price** | **$7,500-10,000** |
| Pilot duration | 2 weeks |

---

## Discovery Questions

Ask these to understand their pain and size the deal:

1. "How does your team find information today?" (surface the pain)
2. "What systems do you use?" (M365, Google, Confluence — determines connectors needed)
3. "How many people would use this?" (size the deal)
4. "Have you tried anything else?" (understand why competitors failed)
5. "What would solving this be worth to your company?" (anchor value, not cost)

---

## Questions They Will Ask

### About the product

**"What exactly does this do?"**
Your team opens a web chat, types a question, gets a direct answer with the source file and page number. Under the hood, two search methods run on every query — keyword matching (finds exact terms like contract numbers, dates, names) and semantic search (understands meaning, so "payment terms" also finds "billing schedule"). This hybrid approach catches what either alone would miss.

**"How is this different from Copilot?"**
Copilot searches everything across all of M365 — $30/user/month. CodeSight is scoped: "search only these 200 contracts." Cost: $50-200/month total, not per user. No M365 dependency. Search is 100% local. If you already have Copilot and it's working, you don't need this. If you don't, or you need scoped project search, or you can't send data to Microsoft — that's where we fit.

**"Can't we just upload to ChatGPT / Claude?"**
Three problems: (1) File limits — you upload a few docs, we index entire folders. (2) No persistence — each chat starts fresh, we maintain a permanent index. (3) Retrieval quality — we use hybrid BM25+vector+RRF, same approach as production search engines. Plus $20/user/month and your data goes to OpenAI/Anthropic.

**"We already have SharePoint search."**
SharePoint finds files by name. It can't answer "What are the payment terms across all vendor contracts?" CodeSight answers questions, not just finds files. It sits alongside your storage, doesn't replace it.

**"What documents can it handle?"**
PDF, Word, PowerPoint, code (10 languages), markdown, text files. Excel and email planned. Scanned PDFs (OCR) planned.

### About privacy

**"Where does our data go?"**
Search and indexing: nowhere. Everything runs on the machine. No internet needed. Answer synthesis: your choice — your own Claude API key, your Azure OpenAI tenant, or a fully local model via Ollama with zero network activity. We are never in the middle. You own the API key.

**"Can we run this completely offline?"**
Yes. Local embedding model + Ollama. Zero internet after initial setup. Works in airplane mode. I'll demonstrate this.

**"How do we verify?"**
Open source. You can read every line. Search works with WiFi off — I'll show you in the demo.

**"What about access controls?"**
Currently, everyone with web UI access can search everything indexed. For most engagements (one team, one project), that's fine. For multi-team deployments with different access levels, that's on the roadmap — in the meantime, run separate instances per team.

### About cost

**"How much?"**
Software: free (open source). Search: free (runs locally). AI answers: ~$0.01-0.03 per question via API, or free with local LLM. Consulting: **$7,500-10K pilot** (one project, two weeks), $3-5K per additional project, $1-2K/month maintenance.

**"Why pay for consulting if the software is free?"**
Speed (deployed in hours, not weeks), configuration (right LLM and embedding for your security requirements), customization (tuned for your document types), training, ongoing support.

**"What's cheaper — this or Azure AI Search?"**

| | CodeSight | Azure AI Search + Azure OpenAI |
|--|-----------|-------------------------------|
| Monthly cost (50 users) | $50-200 (API calls only) | $500-2,000 (search units + API) |
| Setup time | Hours | Weeks |
| Developer needed | No | Yes (Azure experience required) |
| Vendor lock-in | None | Azure |

### About scaling

**"How many users can it handle?"**

| Users | Deployment | LLM backend |
|-------|-----------|-------------|
| 1-10 | Laptop or VM | Ollama or API |
| 20-50 | VM or Docker | Claude/Azure OpenAI API |
| 100+ | Docker + FastAPI + auth | Azure OpenAI |

Search scales easily (local computation). Bottleneck is LLM answers — API backends scale infinitely.

---

## Objections — Quick Reference

| They say | You say |
|----------|---------|
| "We have Copilot" | "Copilot searches everything at $30/user. This gives each project focused search for $50-200/month total." |
| "We'll build it ourselves" | "Your developer spends 2-4 weeks building what's running here today. And they'll build vector-only — no hybrid, worse results." |
| "Data privacy concerns" | "Search runs on your machine. I'll demo it with WiFi off. Open source — audit every line." |
| "Too expensive" | "Your team loses $X/month searching. This pays for itself in weeks." |
| "We'll think about it" | "Totally fair. Want to try a free 30-minute test with your actual documents right now?" |
| "Isn't this just RAG?" | "RAG is the category. Most use basic vector search. We use hybrid BM25+vector+RRF — that's what production search engines use." |
| "What if we outgrow it?" | "Built for scoped collections (hundreds to thousands of docs). If you reach millions org-wide, you'll want Glean. This engagement tells you exactly what you'd need." |
| "Can't we just use Claude Projects?" | "20-30 file limit, no persistent index, $20/user/month, data goes to Anthropic. This handles thousands of docs, local search." |

---

## Demo Script

### Setup (before the meeting)

```bash
python -m codesight index /path/to/their-sample-docs
python -m codesight demo
```

### During the meeting

1. Open the web chat UI
2. "Let me show you. These are your documents. Ask me anything about them."
3. Let THEM type the first question — something they know the answer to
4. Show the answer with source citations
5. Click the source to show exactly where it came from
6. Ask something harder — a cross-document question
7. Turn off WiFi and search again: "This is running on this laptop right now. No cloud."

### Key lines during demo

- "This indexed your folder in X seconds"
- "Search is on this laptop. No cloud, no API, no data leaving"
- "The answer came from [file], page [X] — verify it yourself"
- "Update a document, re-index — only changed parts reprocess"

---

## Closing the Meeting

**Always end with a specific next step.**

Best closing lines:
1. "Want to try right now with your actual documents? I'll index a folder in 30 seconds."
2. "Pick one project. Working system in a week. $7,500, money-back guarantee."
3. "I'll send the proposal tomorrow. Thursday or Friday to discuss?"

**Never say:**
- "Let me know what you think" (passive, no commitment)
- "We can do anything you need" (unfocused, sounds desperate)
- "It depends" without immediately following with specifics
