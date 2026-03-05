# AI-Powered Document Search for [Company Name]

> Copy to `proposals/clients/<name>/proposal.md` and fill in the brackets.

**Prepared by:** Camilo Martinez
**Date:** [YYYY-MM-DD]

---

## Executive Summary

[Company Name] has [X] employees working across [X] projects. Your team searches for information across [SharePoint / shared drives / email] — a process that takes 15-30 minutes per query and costs an estimated **$[X]/month in lost productivity**.

We deploy an AI-powered search system that makes your existing documents instantly searchable. Your team asks questions in plain English and gets precise answers with source citations — in seconds.

**Pilot investment:** $7,500 for 2 weeks on one project. Money-back guarantee.

---

## The Problem

[2-3 sentences from the discovery call — what they told you about their specific pain.]

**The cost of doing nothing:**
- [X] employees x [X] searches/day x 15 min each x $[hourly rate]
- = **$[X]/month in lost productivity**
- Plus: knowledge loss when people leave, decisions delayed waiting for information, duplicate work because teams can't find existing docs.

---

## What We Deploy

A hybrid AI search engine that combines keyword matching with semantic understanding. Unlike SharePoint search or ChatGPT uploads, it:

- **Answers questions**, not just finds files — "What are the payment terms in the Acme contract?" returns the actual answer with the page number
- **Searches across all documents** — finds information scattered across multiple files
- **Runs on your infrastructure** — no data leaves your network

### How it works

```
Your team opens web chat
    -> Types: "What did we agree with [vendor] about delivery dates?"
    -> Gets: "According to the Service Agreement (page 12),
             delivery is due within 30 days of purchase order..."
    -> Clicks source to see the exact document and page
```

### What gets indexed

| Document Type | Examples |
|--------------|---------|
| [Contracts] | [Vendor agreements, service contracts, NDAs] |
| [Policies] | [SOPs, compliance docs, employee handbook] |
| [Project docs] | [Specs, meeting notes, status reports] |

### Technical approach

| Component | How |
|-----------|-----|
| **Search** | Hybrid BM25 + vector with Reciprocal Rank Fusion |
| **Documents** | PDF, Word, PowerPoint, text files, code |
| **Indexing** | Local embedding model — no data sent anywhere |
| **Answers** | [Claude API / Azure OpenAI / local LLM] — your choice |
| **Interface** | Web chat accessible from any browser |
| **Hosting** | [Your server / your cloud VM / your laptop] |

### Data privacy

- Search and indexing: **100% local**. No internet needed.
- Answer synthesis: goes to the LLM provider you choose — you own the API key.
- We are never in the middle. No data flows through us.
- Open source — you can audit every line of code.

---

## Engagement

### Phase 1: Pilot — 2 weeks, $7,500

| Week | What you get |
|------|-------------|
| **Week 1** | Audit document structure, index [pilot project], configure search |
| **Week 2** | Deploy web chat, train power users, test with real questions, tune results |

**Done when:** Your team searches [pilot scope] and gets accurate answers with citations.

**Money-back guarantee:** If the pilot doesn't save your team time, you pay nothing.

### Phase 2: Scale — $3,000-5,000 per project

| What | Details |
|------|---------|
| Additional projects | Index remaining departments/projects |
| Team training | Train full team on effective questioning |
| Search tuning | Optimize for your document types and terminology |

### Phase 3: Maintenance — $1,000-2,000/month

| What | Details |
|------|---------|
| Monitoring | Index freshness, search quality checks |
| Reindexing | Automatic refresh as documents change |
| Support | Hours/month for questions, tuning, new document types |

---

## Pricing Summary

| Phase | Timeline | Investment |
|-------|----------|-----------|
| **Pilot** | 2 weeks | $7,500 |
| **Additional projects** | 1-2 weeks each | $3,000-5,000 each |
| **Monthly maintenance** | Ongoing | $1,000-2,000/month |
| **LLM API cost** | Ongoing | ~$50-200/month |

**Year 1 estimate (pilot + 2 projects + maintenance):** $20,000-30,000
**Compared to:** Microsoft Copilot at $30/user/month = $[X x 12 x 30]/year

**Terms:** 50% upfront, 50% on delivery.

---

## Why Us

1. **Working product.** You've seen the demo with real documents — not slides.
2. **Speed.** Working system in days, not months.
3. **Privacy.** Your data never leaves your infrastructure. Open source, auditable.
4. **Cost.** Fraction of Copilot ($30/user/mo) or Glean ($45/user/mo).
5. **No lock-in.** Open source. If you stop working with us, the system keeps running.

---

## Next Step

Let's start with the pilot: one project, two weeks, $7,500.

Pick the folder of documents your team struggles with most. I'll have it searchable within days.

**Contact:** [email] | [phone]
