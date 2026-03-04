#!/usr/bin/env python3
"""Seed M365 account with fake company data for CodeSight testing.

Populates a Microsoft 365 account with realistic content for Baruch Technologies
(a fictional AI/tech consulting firm) across OneDrive, Outlook, and OneNote.

Usage:
    python scripts/seed_m365.py

Requires:
    CODESIGHT_M365_CLIENT_ID and CODESIGHT_M365_TENANT_ID in .env
    The M365 account must have Files.ReadWrite, Mail.Send, Notes.ReadWrite scopes.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import httpx
from codesight.connectors.m365_auth import M365Authenticator

GRAPH = "https://graph.microsoft.com/v1.0"
RECIPIENT = "JuanMartinez@codesightdev.onmicrosoft.com"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def get_token() -> str:
    auth = M365Authenticator()
    return auth.get_access_token()


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# OneDrive file content definitions
# ---------------------------------------------------------------------------

DRIVE_FILES: dict[str, str] = {
    # --- HR ---
    "remote-work-policy.md": """\
# Remote Work Policy — Baruch Technologies
**Effective Date:** March 15, 2026
**Owner:** People Operations
**Version:** 2.1

## 1. Policy Statement

Baruch Technologies supports flexible remote work arrangements for all full-time
employees. This policy defines eligibility requirements, expectations, and the
equipment reimbursement program as of Q1 2026.

## 2. Eligibility

All employees who have completed their 90-day onboarding period are eligible
for remote work. Contract staff assigned to Project Atlas or Project Beacon may
work remotely subject to client approval (see SOW sections 4.2 and 4.2 of
master-service-agreement.md).

## 3. Work Hours and Availability

- Core hours: 10:00 AM – 3:00 PM in the employee's local timezone.
- Employees must respond to Slack messages within 2 hours during core hours.
- All-hands meetings are held the first Tuesday of each month at 11:00 AM ET.
  See "Q1 All-Hands Meeting Notes" in your email for the March agenda.

## 4. Equipment Reimbursement

| Category | Annual Cap | Approval Required |
|----------|-----------|-------------------|
| Monitor / peripherals | $600 | Manager |
| Internet subsidy | $1,200 | Auto-approved |
| Ergonomic chair | $800 | HR Director |
| Home office setup (new hire) | $1,500 | HR Director |

Submit receipts via Expensify within 30 days of purchase. See expense-policy.md
for full reimbursement procedures.

## 5. Security Requirements

Remote employees must comply with all requirements in the AI Infrastructure
Guide (ai-infrastructure-guide.md), including:
- VPN connection when accessing internal systems.
- Full-disk encryption on all work devices.
- No client data on personal storage (Dropbox, personal iCloud, etc.).

## 6. Performance Expectations

Remote employees are evaluated on output, not hours. Sprint velocity and
project deliverables are the primary metrics. Managers review remote work
eligibility quarterly. Repeated missed sprint goals may result in an in-office
requirement for a 60-day remediation period.

## 7. Policy Violations

Violations of this policy, particularly security requirements, may result in
disciplinary action up to and including termination. Report suspected violations
to compliance@baruchtech.io or anonymously via the ethics hotline.

---
*Last reviewed by Sarah Chen (People Ops) and Raj Patel (CISO) on 2026-03-01.*
""",
    # ---
    "employee-handbook.md": """\
# Employee Handbook — Baruch Technologies
**Version:** 4.0 | **Published:** January 6, 2026

## Welcome from the CEO

Welcome to Baruch Technologies. We are a 23-person AI consulting firm
headquartered in Austin, TX with remote employees across North America.
Our mission is to help mid-market companies deploy AI systems that actually
work in production — not just demos.

## Our Values

1. **Ship working software.** Prototypes are not products.
2. **Client outcomes over billable hours.** We bill flat project fees.
3. **Psychological safety.** Bring problems to light early.
4. **Continuous learning.** 10% of paid hours are protected for learning.

## Employment Classifications

| Type | Benefits | Equity | Remote |
|------|----------|--------|--------|
| Full-time (salaried) | Full | 0.1%–2.0% | Yes |
| Part-time (20+ hrs) | Partial | No | Yes |
| Contractor | None | No | Yes |

## Compensation & Review

Compensation bands are published internally on Notion. Market adjustments
happen each January. Performance bonuses (5–20% of base) are tied to:
- Client NPS scores (40%)
- Sprint velocity targets (30%)
- Peer review scores (30%)

## Time Off

See pto-policy.md for full details. Summary:
- 20 days PTO per year (accrues monthly, no rollover cap in Year 1)
- 11 federal holidays
- Unlimited sick leave (no approval required for < 3 consecutive days)
- 12 weeks parental leave (fully paid, available after 6 months tenure)

## Code of Conduct

All employees must complete the annual ethics training by January 31.
The NDA template (nda-template.md) applies to all client engagements.
Conflicts of interest must be disclosed to your manager and HR within 5 days.

## Benefits Summary

- Health: United HealthCare Choice Plus PPO (company pays 80%)
- Dental: Delta Dental (company pays 100% for employee)
- Vision: VSP (company pays 100% for employee)
- 401(k): 4% match, vested immediately
- L&D budget: $2,000/year per employee (no approval needed under $500)

Benefits enrollment window opens each October. See "Benefits Enrollment
Deadline Reminder" email for the 2026 deadline.

## Contact

- People Ops: people@baruchtech.io
- IT Helpdesk: it@baruchtech.io
- Ethics Hotline: ethics.baruchtech.io (anonymous)
""",
    # ---
    "pto-policy.md": """\
# PTO Policy — Baruch Technologies
**Effective:** January 1, 2026
**Owner:** People Operations

## Accrual Schedule

PTO accrues at 1.67 days per month (20 days/year). Accrual begins on the
first day of employment. There is no waiting period.

| Tenure | Annual PTO | Accrual Rate |
|--------|-----------|--------------|
| 0–2 years | 20 days | 1.67 days/month |
| 2–5 years | 25 days | 2.08 days/month |
| 5+ years | 30 days | 2.50 days/month |

## Rollover

Up to 10 days may roll over into the next calendar year. Days beyond the
10-day rollover cap are forfeited on December 31. Exceptions require VP
approval and must be documented in HRIS by December 15.

## Request Process

1. Submit request in Rippling at least **5 business days** in advance for
   planned time off (1+ days). Same-day requests for illness do not require
   advance notice.
2. Manager approves or denies within 2 business days.
3. For absences of 3+ consecutive days (non-illness), project leads must be
   notified to ensure sprint coverage. See ai-infrastructure-guide.md for
   on-call rotation handoff procedures.

## PTO Payout on Separation

Accrued, unused PTO is paid out at termination at the employee's current
base rate, regardless of reason for separation. Texas law does not require
this, but it is our policy.

## Holidays (2026)

- Jan 1 (New Year's Day)
- Jan 19 (MLK Day)
- Feb 16 (Presidents' Day)
- May 25 (Memorial Day)
- Jul 3 (Independence Day observed)
- Sep 7 (Labor Day)
- Nov 26 (Thanksgiving)
- Nov 27 (Day after Thanksgiving)
- Dec 24 (Christmas Eve)
- Dec 25 (Christmas Day)
- Dec 31 (New Year's Eve)

## Bereavement

Up to 5 days paid bereavement leave for immediate family (spouse, child,
parent, sibling). Up to 3 days for extended family.

---
*Questions: people@baruchtech.io*
""",
    # --- Finance ---
    "q1-2026-financial-report.md": """\
# Q1 2026 Financial Report — Baruch Technologies
**Period:** January 1 – March 31, 2026
**Prepared By:** Finance Team
**Confidential — Internal Use Only**

## Executive Summary

Q1 2026 revenue of **$1,247,500** is 14% above Q1 2025 actuals ($1,094,000)
and 3% above Q1 2026 budget ($1,210,000). Gross margin held at 68%, consistent
with Q4 2025. The primary driver of outperformance was Project Atlas (Meridian
Corp) exceeding Phase 1 scope, generating $87,500 in additional milestone
billings.

## Revenue by Client

| Client | Q1 2026 | Q4 2025 | YoY Change |
|--------|---------|---------|-----------|
| Meridian Corp (Project Atlas) | $487,500 | $375,000 | +30% |
| Apex Industries (ongoing) | $312,000 | $312,000 | 0% |
| Northgate Capital | $185,000 | $210,000 | -12% |
| New logos (3 clients) | $263,000 | $0 | N/A |
| **Total** | **$1,247,500** | **$897,000** | **+39%** |

*Note: Q4 2025 revenue excludes $197,000 deferred from Project Beacon
pre-sales that recognized in Q1 2026.*

## Key Expenses

| Category | Q1 2026 | Budget | Variance |
|----------|---------|--------|---------|
| Salaries & Benefits | $512,000 | $510,000 | +$2,000 |
| Cloud Infrastructure (AWS) | $43,800 | $40,000 | +$3,800 |
| GPU Cluster (new — see budget-approval email) | $28,500 | $0 | +$28,500 |
| Contractor Payments | $117,000 | $125,000 | -$8,000 |
| Marketing & Events | $22,000 | $25,000 | -$3,000 |
| G&A | $38,200 | $38,000 | +$200 |
| **Total OpEx** | **$761,500** | **$738,000** | **+$23,500** |

## Cash Position

- Cash on hand (March 31): **$2,103,400**
- AR outstanding (>30 days): **$187,500** (Apex Industries — see Q1 invoice)
- Runway at current burn: 26 months

## Q2 2026 Outlook

Q2 revenue target: $1,350,000 (based on Project Beacon Phase 1 kickoff
confirmed for April 14 — see "Project Beacon Kickoff Date Confirmed" email).
Primary risk: Northgate Capital renewal discussions in progress (see
"Renewal Discussion - Apex Industries" email for context on pricing strategy).

---
*Next review: CFO + CEO sync on April 15, 2026.*
""",
    # ---
    "expense-policy.md": """\
# Expense Policy — Baruch Technologies
**Effective:** January 1, 2026
**Owner:** Finance

## General Principles

All business expenses must be:
1. Ordinary and necessary for business operations.
2. Submitted within **30 days** of the transaction date.
3. Accompanied by an itemized receipt (credit card statement not sufficient).

## Expense Limits by Category

| Category | No Approval | Manager Approval | VP Approval |
|----------|------------|-----------------|-------------|
| Meals (solo) | ≤$50 | $51–$100 | >$100 |
| Meals (team, per person) | ≤$75 | $76–$150 | >$150 |
| Travel (per trip) | ≤$500 | $501–$2,000 | >$2,000 |
| Software subscriptions | ≤$100/mo | $101–$500/mo | >$500/mo |
| Hardware | ≤$200 | $201–$1,000 | >$1,000 |
| Client entertainment | N/A | ≤$250/person | >$250/person |

## Travel Policy

- Flights: Economy class for domestic, Economy/Premium Economy for
  international (flights >6 hours).
- Hotels: ≤$250/night in major cities, ≤$180/night elsewhere.
- Per diem: $75/day (meals + incidentals) when not submitting actual receipts.
- Car rental: Economy class unless 3+ employees traveling together.
- Book through TravelPerk where possible (preferred rates negotiated).

## Submission Process

1. Log expenses in Expensify within 30 days.
2. Attach receipts (photo from phone is acceptable).
3. Select the correct project code (Atlas: P-2024-ATL, Beacon: P-2025-BCN,
   Apex Industries: P-2023-APX, Northgate: P-2023-NGT, G&A: GA-2026).
4. Manager receives auto-approval request via email.
5. Finance reviews and reimburses by the 15th or last day of the month.

## Non-Reimbursable Items

- Alcohol (unless client entertainment, manager-approved)
- Fines, penalties, parking tickets
- Personal travel add-ons (seat upgrades for personal preference)
- Gym memberships (unless medical necessity, requires HR approval)
- Any purchase for personal benefit

---
*Questions: finance@baruchtech.io | Monthly report due the 5th of each month.*
""",
    # ---
    "pricing-sheet.md": """\
# Pricing Sheet — Baruch Technologies
**Version:** Q1 2026 | **Confidential — Do Not Share Without NDA**

## Service Lines

### 1. AI Readiness Assessment
Evaluate data infrastructure, team capabilities, and identify highest-ROI use
cases for AI adoption.

| Tier | Deliverable | Price |
|------|------------|-------|
| Lite (1 week) | Executive report + 3 use case briefs | $12,500 |
| Standard (2 weeks) | Full assessment + prioritized roadmap + exec presentation | $22,500 |
| Enterprise (4 weeks) | Full assessment + vendor selection + POC scoping | $45,000 |

### 2. AI Implementation Projects

Fixed-fee project delivery. Price includes all engineering, PM, and QA.

| Project Type | Typical Duration | Price Range |
|-------------|-----------------|-------------|
| RAG document search (like CodeSight) | 4–6 weeks | $75,000–$95,000 |
| ML pipeline (training + serving) | 6–10 weeks | $120,000–$180,000 |
| LLM fine-tuning + evaluation | 4–8 weeks | $85,000–$140,000 |
| AI agent / workflow automation | 6–12 weeks | $95,000–$200,000 |
| Data platform modernization | 8–16 weeks | $150,000–$350,000 |

### 3. Managed AI Operations

Ongoing support and model monitoring after project delivery.

| Tier | SLA | Monthly Price |
|------|-----|--------------|
| Basic (email support, monthly review) | 48-hour response | $3,500/mo |
| Standard (Slack + monthly review) | 24-hour response | $6,500/mo |
| Premium (dedicated Slack + weekly review) | 4-hour response | $12,000/mo |

## Current Client Rates

- Meridian Corp (Project Atlas): $487,500 flat (Phases 1–3 combined)
- Apex Industries (ongoing): $312,000/year managed services (Premium tier)
- Northgate Capital: $210,000/year (Standard tier, renewal pending)

## Discount Policy

- Volume: >$200K/year = 5% discount; >$500K/year = 10% discount
- Non-profit: 20% discount (board approval required)
- Referral: 3% credit to referring client on next invoice

---
*For custom quotes, contact: sales@baruchtech.io*
""",
    # --- Projects ---
    "project-atlas-sow.md": """\
# Statement of Work: Project Atlas — Phase 1
**Client:** Meridian Corp
**Vendor:** Baruch Technologies
**Effective Date:** October 15, 2025
**Project Code:** P-2024-ATL

## 1. Project Overview

Baruch Technologies ("Vendor") will design, build, and deploy a production-ready
AI-powered document search and question-answering system for Meridian Corp's
internal legal and compliance document library (~45,000 documents, primarily
PDF and DOCX format).

This system will enable Meridian's 120 legal and compliance staff to search
across all documents using natural language queries and receive AI-synthesized
answers with source citations.

## 2. Scope of Work

### Phase 1 Deliverables (this SOW)

1. **Document ingestion pipeline** — automated ingestion of new and updated
   documents from Meridian's SharePoint environment via Microsoft Graph API.
2. **Hybrid search index** — BM25 + vector search with RRF ranking over all
   45,000 documents.
3. **Question-answering interface** — Streamlit web UI with Claude API backend,
   deployed on Meridian's Azure tenant.
4. **Access control integration** — Azure AD group-based document access
   permissions respected at query time.
5. **Admin dashboard** — index freshness monitoring, ingestion error alerts.
6. **Documentation** — deployment runbook, user guide, admin guide.

### Out of Scope

- Mobile application
- Integration with Meridian's ticketing system (Jira)
- Training data for fine-tuned models (covered in Phase 3 if exercised)

## 3. Timeline

| Milestone | Target Date | Payment |
|-----------|-------------|---------|
| Kickoff + requirements sign-off | Oct 22, 2025 | $75,000 |
| Search index live (beta) | Nov 28, 2025 | $125,000 |
| QA + UAT complete | Dec 19, 2025 | $100,000 |
| Production deployment | Jan 16, 2026 | $100,000 |
| Phase 1 final acceptance | Jan 30, 2026 | $87,500 |
| **Total Phase 1** | | **$487,500** |

## 4. Client Responsibilities

- Provide read-only SharePoint API credentials by Oct 20, 2025.
- Provide Azure AD app registration with required permissions by Oct 20, 2025.
- Designate a technical point of contact (Meridian IT) and a business owner.
- Complete UAT within 10 business days of beta delivery.

## 5. Acceptance Criteria

- Search returns relevant results for 95% of 50 benchmark queries (provided
  by Meridian's legal team).
- End-to-end query response time < 3 seconds (p95) under 20 concurrent users.
- Document ingestion latency < 4 hours from SharePoint update to searchable.

## 6. Payment Terms

Net-30 from invoice date. Late payments accrue 1.5% monthly interest.
Invoices will be sent to: ap@meridiancorp.com

---
*Authorized Signatures Required — See Master Service Agreement (master-service-agreement.md)*
""",
    # ---
    "project-atlas-architecture.md": """\
# Project Atlas — Technical Architecture
**Client:** Meridian Corp
**Author:** Engineering Team, Baruch Technologies
**Date:** November 3, 2025
**Version:** 1.2

## System Overview

Project Atlas deploys a hybrid AI search system on Meridian's Azure tenant.
All data remains within Meridian's Azure subscription at all times.

```
SharePoint Online (Meridian)
         |
         | Microsoft Graph API (delta sync)
         v
+---------------------------+
|  Ingestion Service        |  Azure Container App
|  (Python + httpx)         |  Runs hourly, picks up deltas
+-----------+---------------+
            |
            | Document chunks + embeddings
            v
+---------------------------+    +---------------------------+
|  Vector Store (pgvector)  |    |  Full-Text Index (SQLite) |
|  Azure PostgreSQL Flex    |    |  Azure Blob (NFS mount)   |
+---------------------------+    +---------------------------+
            \\                               /
             \\     Hybrid RRF Retrieval    /
              +---------------------------+
              |   Search API (FastAPI)    |  Azure Container App
              +---------------------------+
                           |
              +---------------------------+
              |   Chat UI (Streamlit)     |  Azure Container App
              |   + Azure AD SSO          |
              +---------------------------+
                           |
              +---------------------------+
              |  Claude API (claude-3-7)  |  External — Anthropic
              |  Answer synthesis only    |
              +---------------------------+
```

## Key Design Decisions

### ADR-001: Use pgvector instead of LanceDB
LanceDB is excellent for local deployments (used in CodeSight OSS) but
requires file system access. Meridian's deployment target is Azure Container
Apps (stateless), making PostgreSQL + pgvector the better choice.
Cost: ~$180/month for Azure PostgreSQL Flexible Server (Standard_D2s_v3).

### ADR-002: Azure AD pass-through for document permissions
Documents in SharePoint have item-level permissions. We propagate these to the
search index via a permission mapping table (user_id → [doc_ids]) that is
refreshed every 6 hours. Queries filter by the authenticated user's doc list
at retrieval time (not index time). This avoids re-indexing on permission changes.

### ADR-003: Claude API for answer synthesis only
Embeddings use text-embedding-3-small (OpenAI) for cost efficiency
($0.02/1M tokens vs. $0.13/1M for text-embedding-3-large). Answer synthesis
uses claude-3-7-sonnet — Meridian's legal team requires answer accuracy over
cost. All data sent to APIs is chunk text (no PII from original documents per
Meridian's DPA review — see data-processing-agreement.md).

## Infrastructure Costs (estimated monthly)

| Component | SKU | Monthly |
|-----------|-----|---------|
| Ingestion service | Container App (Consumption) | $15–$40 |
| PostgreSQL + pgvector | Standard_D2s_v3, 100GB SSD | $185 |
| Search + Chat API | Container App (Dedicated D2) | $145 |
| Azure Blob Storage | 500GB LRS | $10 |
| Claude API (est. 10K queries/mo) | claude-3-7-sonnet | $120–$180 |
| Embedding API | text-embedding-3-small | $5–$15 |
| **Total** | | **~$480–$575/mo** |

## Sprint Status

- Sprint 1 (Nov 3–14): Ingestion pipeline complete, delta sync tested.
- Sprint 2 (Nov 17–28): Search index live, RRF tuning in progress.
- Sprint 3 (Dec 1–12): Chat UI, AD SSO, admin dashboard (current sprint).
  See "Project Atlas Sprint 3 Update" email for latest status.
""",
    # ---
    "project-beacon-proposal.md": """\
# Project Beacon — Proposal
**Prospect:** Falcon Ridge Financial
**Prepared By:** Baruch Technologies Sales Team
**Date:** February 10, 2026
**Proposal Version:** 1.0

## Executive Summary

Baruch Technologies proposes to build "Project Beacon" — an AI-powered
investment research assistant for Falcon Ridge Financial's 45-person research
team. The system will ingest and search across 10 years of internal research
memos, earnings call transcripts, and market analysis reports (~200,000
documents), providing analysts with instant, cited answers to research queries.

Estimated engagement: **$165,000** (Phase 1), 10 weeks, starting April 14, 2026.
See "Project Beacon Kickoff Date Confirmed" email for final schedule.

## Problem Statement

Falcon Ridge's research team spends an estimated 3–4 hours per analyst per day
searching for relevant prior research. With 45 analysts at an average fully-
loaded cost of $350/hour, this represents **$2.3M/year in lost productivity**.
Additionally, institutional knowledge walks out the door when senior analysts
depart — there is no searchable record of past research decisions.

## Proposed Solution

A hybrid AI search system (same architecture as Project Atlas for Meridian
Corp — proven in production since January 2026) customized for financial
research workflows:

- **Semantic search** over all internal documents with cited answers.
- **Time-filtered queries**: "What did our analysts say about NVDA in Q3 2024?"
- **Cross-reference detection**: AI identifies related research across time.
- **Bloomberg terminal integration** (Phase 2): ingest real-time market data
  alongside internal docs.

## Implementation Plan

| Phase | Scope | Duration | Price |
|-------|-------|----------|-------|
| 1: Core system | Ingestion + search + UI | 10 weeks | $165,000 |
| 2: Bloomberg integration | Real-time data feed | 6 weeks | $85,000 |
| 3: Fine-tuning | Domain-adapted embeddings | 4 weeks | $65,000 |
| Managed ops (post-launch) | Premium tier | Ongoing | $12,000/mo |

## Why Baruch Technologies

- **Proven reference**: Meridian Corp (Phase 1 live since Jan 2026, 95%
  accuracy on benchmark queries, <2.1s p95 response time).
- **Financial services experience**: Deployed 3 AI systems in fintech; compliant
  with SOC 2 Type II and understanding of SEC retention requirements.
- **No vendor lock-in**: All code owned by Falcon Ridge. Open architecture,
  no proprietary runtime fees.

---
*Next step: Technical discovery call with Falcon Ridge IT. Contact: sales@baruchtech.io*
""",
    # --- Legal ---
    "master-service-agreement.md": """\
# Master Service Agreement
**Between:** Baruch Technologies, Inc. ("Company") and the Client identified
in each Statement of Work
**Version:** 3.2 | **Last Updated:** January 15, 2026

## 1. Services

Company will perform the services described in each Statement of Work ("SOW")
executed under this Agreement. Each SOW is incorporated by reference and
constitutes part of this Agreement. In the event of conflict, the SOW controls.

## 2. Payment Terms

2.1 Client shall pay all invoices within thirty (30) days of receipt.
2.2 Invoices not paid within thirty (30) days accrue interest at 1.5% per month.
2.3 Company may suspend services upon fifteen (15) days written notice if any
    invoice is more than forty-five (45) days past due.
2.4 All fees are in USD and exclusive of applicable taxes.

## 3. Intellectual Property

3.1 **Client IP**: All deliverables created specifically for Client under a SOW
    become Client's property upon full payment.
3.2 **Company IP**: Company retains all rights to pre-existing IP, tools,
    frameworks, and general methodologies. Company grants Client a perpetual,
    royalty-free license to use any Company IP embedded in deliverables.
3.3 **Open Source**: Deliverables may include open-source components. Client
    is responsible for compliance with applicable open-source licenses.

## 4. Confidentiality

Each party agrees to hold the other's Confidential Information in strict
confidence. See nda-template.md for the full NDA terms incorporated herein.
Confidential Information does not include information that (a) is or becomes
publicly known through no wrongful act, (b) was rightfully known before
disclosure, or (c) is independently developed without reference to confidential
information.

## 5. Data Processing

For engagements involving Client's personal data, the parties will execute
the Data Processing Agreement (data-processing-agreement.md) as an addendum.
Company is a data processor; Client is the data controller.

## 6. Limitation of Liability

IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY EXCEED THE TOTAL FEES
PAID OR PAYABLE UNDER THE APPLICABLE SOW IN THE TWELVE (12) MONTHS PRECEDING
THE CLAIM. NEITHER PARTY SHALL BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL,
OR CONSEQUENTIAL DAMAGES.

## 7. Governing Law

This Agreement shall be governed by the laws of the State of Texas, without
regard to conflict of law principles. Disputes shall be resolved by binding
arbitration in Austin, TX under AAA Commercial Rules.

## 8. Term and Termination

This Agreement commences on the Effective Date and continues until terminated.
Either party may terminate this Agreement on sixty (60) days written notice.
SOWs in progress at termination are completed per their terms unless terminated
for cause. Termination for cause (material breach uncured within 30 days)
permits immediate termination.

---
*Questions: legal@baruchtech.io*
""",
    # ---
    "nda-template.md": """\
# Non-Disclosure Agreement (Template)
**Baruch Technologies, Inc.**
**Version:** 2.1 | **Last Updated:** December 1, 2025

## Parties

This Non-Disclosure Agreement ("Agreement") is entered into as of the date
signed ("Effective Date") between:

- **Disclosing Party**: [COMPANY NAME], a [STATE] [ENTITY TYPE]
- **Receiving Party**: Baruch Technologies, Inc., a Delaware corporation
  ("Baruch"), or vice versa, as applicable.

## 1. Definition of Confidential Information

"Confidential Information" means any non-public information disclosed by one
party ("Disclosing Party") to the other ("Receiving Party"), either directly
or indirectly, in writing, orally, or by inspection of tangible objects,
that is designated as confidential or that reasonably should be understood
to be confidential given the nature of the information and the circumstances
of disclosure. This includes but is not limited to: business plans, technical
specifications, client lists, financial information, and source code.

## 2. Obligations

The Receiving Party agrees to:
(a) Hold Confidential Information in strict confidence;
(b) Not disclose Confidential Information to any third party without prior
    written consent of the Disclosing Party;
(c) Use Confidential Information solely for evaluating or engaging in a
    business relationship with the Disclosing Party;
(d) Limit access to Confidential Information to employees and contractors
    who have a need to know and are bound by written confidentiality obligations
    no less restrictive than this Agreement.

## 3. Term

This Agreement is effective for two (2) years from the Effective Date. The
confidentiality obligations survive termination for five (5) years.

## 4. Exceptions

The obligations of this Agreement do not apply to information that:
(a) Is or becomes publicly known through no wrongful act of the Receiving Party;
(b) Was rightfully in the Receiving Party's possession before disclosure;
(c) Is independently developed by Receiving Party without use of Confidential
    Information; or
(d) Is required to be disclosed by law, regulation, or court order, provided
    the Receiving Party gives prompt notice to allow Disclosing Party to seek
    a protective order.

## 5. Return of Materials

Upon request, the Receiving Party shall promptly return or destroy all
Confidential Information and certify in writing that it has done so.

---
*[SIGNATURE BLOCKS — to be completed per engagement]*
*For new client onboarding, send this template to legal@baruchtech.io for review.*
""",
    # ---
    "data-processing-agreement.md": """\
# Data Processing Agreement
**Between:** Baruch Technologies, Inc. ("Processor") and the Client ("Controller")
**Incorporated into:** Master Service Agreement (master-service-agreement.md)
**Version:** 1.0 | **Effective:** January 1, 2026

## 1. Scope and Purpose

This Data Processing Agreement ("DPA") applies where Baruch Technologies
processes personal data on behalf of the Client in the course of providing
AI/ML services. This DPA supplements and is incorporated into the Master
Service Agreement.

## 2. Roles

- **Controller**: Client determines the purposes and means of processing.
- **Processor**: Baruch Technologies processes data only on Client's documented
  instructions.

## 3. Data Types Processed

As part of AI system deployments (e.g., Project Atlas for Meridian Corp),
Baruch may process:
- Document metadata (author, creation date, modification date)
- Document content (text extracted for indexing — may include names, emails,
  phone numbers incidentally)
- User query logs (anonymized after 30 days unless Client opts out)
- Access logs (IP address, user ID, timestamp)

## 4. Processor Obligations

4.1 Process personal data only on Controller's written instructions.
4.2 Ensure persons authorized to process personal data have committed to
    confidentiality.
4.3 Implement appropriate technical and organizational security measures
    including: encryption at rest (AES-256), encryption in transit (TLS 1.3),
    access control (RBAC), and audit logging.
4.4 Notify Controller within 72 hours of becoming aware of a personal data breach.
4.5 Assist Controller with data subject requests (access, deletion, portability)
    within 30 days.

## 5. Sub-Processors

Baruch Technologies uses the following sub-processors for AI deployments:

| Sub-Processor | Service | Location | DPA |
|--------------|---------|----------|-----|
| Microsoft Azure | Cloud infrastructure | US (East) | Microsoft DPA v2025 |
| Anthropic | LLM API (Claude) | US | Anthropic API ToS |
| OpenAI | Embedding API | US | OpenAI DPA |

Client consents to the above sub-processors. Baruch will notify Client 30 days
before adding new sub-processors.

## 6. Audit Rights

Controller may audit Baruch's compliance with this DPA once per year upon
30 days written notice, or immediately following a data breach.

## 7. Deletion / Return

Upon termination of the MSA, Baruch will delete or return all personal data
within 30 days and provide written certification.

---
*For questions: privacy@baruchtech.io | DPO: Raj Patel (raj@baruchtech.io)*
""",
    # --- Technical ---
    "ai-infrastructure-guide.md": """\
# AI Infrastructure Guide — Baruch Technologies
**Owner:** Engineering Team | **Version:** 2.3 | **Updated:** February 28, 2026

## Overview

This guide covers the internal AI infrastructure used for client project
development and the Baruch internal tooling (including the GPU cluster
approved in the February budget — see "Budget Approval for GPU Cluster" email).

## Development Environment

### Prerequisites

- Python 3.11+ (use `pyenv` or `uv` for version management)
- Docker Desktop 4.x
- AWS CLI v2 (configured for `baruch-dev` and `baruch-prod` profiles)
- `kubectl` 1.29+ for K8s cluster access

### Local Setup

```bash
# Clone and set up
git clone git@github.com:baruch-tech/ai-infra.git
cd ai-infra
uv sync

# Configure environment
cp .env.example .env
# Fill in: OPENAI_API_KEY, ANTHROPIC_API_KEY, AWS_PROFILE

# Start local services
docker compose up -d  # starts Redis, PostgreSQL, pgvector
uv run pytest -q      # verify setup
```

## GPU Cluster

Baruch's new A10G GPU cluster (approved Feb 2026, deployed March 1, 2026)
consists of 4x `g5.xlarge` EC2 instances in AWS us-east-1.

- **Purpose**: Fine-tuning experiments, local embedding models, batch inference
- **Access**: Via AWS SSM Session Manager (`aws ssm start-session --target i-0abc123`)
- **Cost**: ~$28,500/month at current utilization (tracked in Q1 financial report)
- **Reservation**: Reserve time via internal Notion calendar (>2 hour jobs)

## Security Requirements (see also remote-work-policy.md)

- VPN: Tailscale (invite: it@baruchtech.io). Required for all production access.
- MFA: Required on all accounts (AWS, GitHub, GCP). Use TOTP (not SMS).
- Secrets: All secrets in AWS Secrets Manager. No hardcoding. No `.env` files
  in git.
- On-call: Primary on-call rotates weekly. See PagerDuty schedule. Escalation
  procedure in incident-response-playbook.md.

## ML Pipeline

### Training Jobs

Submit jobs via the `baruch-train` CLI:
```bash
baruch-train submit --config jobs/finetune-embeddings.yaml --gpu 2
```

Jobs run on the GPU cluster. Results auto-sync to S3: `s3://baruch-ml-artifacts/`.

### Model Registry

All production models are registered in MLflow at https://mlflow.baruchtech.io.
Use semantic versioning: `model-name/v1.2.3`. Promotion to production requires
two engineer approvals via GitHub PR review.

## Monitoring

- Infrastructure: Datadog (dashboards.baruchtech.io)
- ML metrics: MLflow + custom Grafana dashboards
- Alerts: PagerDuty → Slack #alerts → On-call engineer
- Incident management: See incident-response-playbook.md

---
*Questions: engineering@baruchtech.io | #infra on Slack*
""",
    # ---
    "deployment-runbook.md": """\
# Deployment Runbook — AI Systems
**Owner:** Engineering / DevOps | **Last Updated:** March 2, 2026

## Deployment Environments

| Environment | URL | Branch | Deploy Trigger |
|-------------|-----|--------|---------------|
| Development | dev.baruchtech.io | `develop` | Push to `develop` |
| Staging | staging.baruchtech.io | `main` | PR merge to `main` |
| Production | baruchtech.io | `main` (tagged) | Manual (`v*` tag) |

Client environments are deployed in their own cloud accounts via Terraform.
See Terraform modules at `infra/modules/ai-search-stack/`.

## Standard Deployment (Internal)

```bash
# 1. Ensure all tests pass
uv run pytest -q
uv run ruff check .
uv run mypy src/ --ignore-missing-imports

# 2. Build and push Docker image
VERSION=$(git describe --tags --abbrev=0)
docker build -t baruch-ai:${VERSION} .
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/baruch-ai:${VERSION}

# 3. Deploy to staging
kubectl set image deployment/baruch-ai app=123456789.dkr.ecr.us-east-1.amazonaws.com/baruch-ai:${VERSION} -n staging
kubectl rollout status deployment/baruch-ai -n staging

# 4. Run smoke tests against staging
./scripts/smoke-test.sh https://staging.baruchtech.io

# 5. Tag for production
git tag v${VERSION} && git push --tags

# 6. Deploy to production (triggers GitHub Action)
gh workflow run deploy-prod.yml -f version=${VERSION}
```

## Client Deployment (Azure — Project Atlas)

Project Atlas is deployed in Meridian Corp's Azure tenant. Deployment requires
Meridian IT approval (contact: it-infra@meridiancorp.com).

```bash
# Authenticate to Meridian's Azure tenant
az login --tenant meridian-corp-tenant-id

# Deploy via Bicep template
az deployment group create \
  --resource-group rg-baruch-atlas \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/params.meridian.json
```

## Rollback Procedure

### Kubernetes (Internal)
```bash
kubectl rollout undo deployment/baruch-ai -n production
kubectl rollout status deployment/baruch-ai -n production
```

### Azure Container Apps (Client)
```bash
az containerapp revision deactivate --name baruch-atlas --resource-group rg-baruch-atlas --revision <old-revision>
az containerapp ingress traffic set --name baruch-atlas --resource-group rg-baruch-atlas --revision-weight <stable-revision>=100
```

## Post-Deployment Checks

1. Check Datadog dashboard — error rate < 0.1%, p95 latency < 3s.
2. Verify Slack #alerts is quiet for 10 minutes.
3. Test 3 sample queries in production.
4. Update deployment log in Notion.

## Emergency Contacts

- On-call engineer: PagerDuty (primary escalation)
- DevOps lead: devops@baruchtech.io
- Incident commander: See incident-response-playbook.md
""",
    # ---
    "incident-response-playbook.md": """\
# Incident Response Playbook
**Owner:** Engineering | **Version:** 1.4 | **Updated:** February 28, 2026

## Severity Levels

| Level | Definition | Response Time | Example |
|-------|-----------|--------------|---------|
| P1 (Critical) | Production down, data breach | 15 min | All users unable to query |
| P2 (High) | Degraded performance >20% of users | 30 min | Search returning wrong results |
| P3 (Medium) | Non-critical feature unavailable | 2 hours | Admin dashboard down |
| P4 (Low) | Minor issue, workaround available | Next business day | Slow export feature |

## Incident Response Process

### Step 1: Detection and Triage (0–15 min)
- Alert fires in PagerDuty → on-call engineer acknowledges.
- Open incident channel in Slack: `/incident open P[level] [short description]`
- Assign roles: Incident Commander (IC), Technical Lead, Comms Lead.
- Initial assessment: Is this P1/P2? Escalate if yes.

### Step 2: Containment (15–45 min)
- Identify blast radius: Which clients/users are affected?
  - Project Atlas (Meridian Corp): check Datadog dashboard `atlas-prod`
  - Internal tools: check `baruch-internal` dashboard
- If data breach suspected: immediately notify Raj Patel (CISO) and legal.
  Per our DPA (data-processing-agreement.md), clients must be notified within 72h.
- If system is returning incorrect answers: set search to "degraded mode"
  (returns results only, disables AI answer synthesis).

### Step 3: Investigation
- Review application logs in Datadog (last 30 minutes).
- Check ML pipeline logs in MLflow for recent model changes.
- Review deployment log: was there a recent deployment? See deployment-runbook.md
  for rollback procedure.

### Step 4: Mitigation and Resolution
- Apply fix or rollback. Document all actions in the incident channel.
- Test resolution with smoke tests (./scripts/smoke-test.sh).
- Confirm with on-call: "All systems green."

### Step 5: Post-Incident Review (within 48 hours)
- Write post-mortem document (template: Post-Mortem Template in Notion).
- Post to #engineering Slack channel.
- See "Production Incident Post-Mortem - Feb 28" email for the most recent
  example (ML pipeline misconfiguration, 47-minute P2 incident).

## February 28 Incident Summary

On February 28, 2026, a misconfigured ML pipeline update caused embedding
vectors to be generated with incorrect dimensionality (256d instead of 768d).
This resulted in search quality degradation for 47 minutes.
- Detection: Automated test caught incorrect result count at 14:23 UTC.
- Resolution: Rollback to previous model version at 15:10 UTC.
- Root cause: Missing dimension validation in CI pipeline.
- Action items: Added dimensionality assertion to all embedding pipeline tests.

---
*On-call schedule: PagerDuty | Escalation: devops@baruchtech.io*
""",
}


# ---------------------------------------------------------------------------
# Email content definitions
# ---------------------------------------------------------------------------

EMAILS: list[dict] = [
    {
        "subject": "Project Atlas Sprint 3 Update",
        "body": """\
Hi team,

Wanted to share a quick update on Project Atlas (Meridian Corp) as we close out Sprint 3.

STATUS: On track for December 19 UAT deadline.

Completed this sprint:
- Chat UI is live in staging (https://staging-atlas.baruchtech.io). Login with your baruchtech.io SSO.
- Azure AD integration is working end-to-end — tested with 3 Meridian AD groups.
- Admin dashboard shows index freshness, ingestion error rate, and daily query volume.
- Response time is 1.8s p95 under simulated 20-concurrent-user load (beats 3s SLA in the SOW).

In progress:
- Access control filtering at query time (implementing the permission mapping table described in project-atlas-architecture.md ADR-002). Targeting completion by Dec 10.
- Final UAT test plan document — will share by Dec 8.

Risks:
- Meridian IT hasn't provided updated SharePoint credentials for the prod environment. Sarah Chen is following up with their IT contact. If we don't have these by Dec 12, we may need to push UAT to Dec 22.
- One edge case: documents with restricted permissions (fewer than 5 authorized users) are not showing up in the search index. Looking into whether this is an API permissions issue or a filtering bug.

Next sprint (Dec 15–19) is the UAT sprint — Meridian's legal team will be running the 50 benchmark queries. We need everyone available for rapid bug turnaround during that week.

Full sprint board: https://linear.app/baruch-tech/project-atlas-sprint-3

Let me know if any questions.

Best,
Engineering Team, Baruch Technologies
""",
    },
    {
        "subject": "Project Beacon Kickoff Date Confirmed",
        "body": """\
Hi all,

Great news — Falcon Ridge Financial has signed the Project Beacon SOW. Kickoff is confirmed for April 14, 2026.

Contract details:
- Phase 1: $165,000 (10 weeks, AI search over 200K research documents)
- Phase 2: $85,000 (Bloomberg integration, optional, exercisable by June 30)
- Managed Ops: $12,000/month (Premium tier, starts at Phase 1 acceptance)

Project code: P-2025-BCN (use this for all expense submissions — see expense-policy.md).

Pre-kickoff checklist (action items):
1. [Engineering] Set up P-2025-BCN project in Linear and AWS — by April 7.
2. [Sales] Send Falcon Ridge the DPA for signature — by April 7 (template: data-processing-agreement.md).
3. [People Ops] Confirm team assignments: need 2 senior engineers + 1 PM for full duration. Sarah Chen to handle onboarding if we bring on a contractor.
4. [Finance] Issue the kickoff invoice ($41,250 — first milestone 25% of Phase 1) — by April 14.

Falcon Ridge technical contact: CTO James Okafor (j.okafor@falconridge.com).

We're using the same architecture as Project Atlas (see project-atlas-architecture.md) with modifications for financial data and time-based filtering. The proposal (project-beacon-proposal.md) has the full scope.

Q2 revenue plan now assumes $165K for Beacon Phase 1 plus ongoing Apex and Northgate revenue. See Q1 financial report (q1-2026-financial-report.md) for the Q2 outlook.

Very exciting milestone for the team. Let's make Beacon as successful as Atlas.

Best,
Leadership Team
""",
    },
    {
        "subject": "Q1 Invoice for Meridian Corp",
        "body": """\
Hi Finance,

Please find below the billing details for the Meridian Corp Q1 invoices. Raj can confirm the wire details are correct before sending.

Invoice #INV-2026-0047
Client: Meridian Corp
Project: Atlas (P-2024-ATL)
Period: January 1 – January 30, 2026
Description: Project Atlas Phase 1 — Final Acceptance Milestone
Amount: $187,500 (milestone $87,500 + January managed ops $12,000 × first month setup fee $88,000)

Wait — correction. The milestone payment is $87,500 and there is no managed ops for January (that starts in February per the SOW). The correct amount is $87,500.

Invoice breakdown:
- Phase 1 Final Acceptance Milestone: $87,500
- Total: $87,500

Send to: ap@meridiancorp.com
PO Number: MC-2025-8847 (Meridian provided this on Dec 15)
Net-30 terms (due by March 1, 2026)

Note: There is still $187,500 outstanding from Q4 — the Phase 1 acceptance milestone ($87,500) from January is unpaid as of today. Total AR from Meridian: $87,500 (new) + $100,000 (Dec invoice, 45 days past due). Please send a payment reminder per the MSA (master-service-agreement.md section 2.2). Interest accrual kicks in tomorrow.

The Q1 financial report (q1-2026-financial-report.md) shows this AR in the cash flow section.

Thank you,
Finance Team
""",
    },
    {
        "subject": "Renewal Discussion - Apex Industries",
        "body": """\
Hi,

Heads up on the Apex Industries renewal — their current contract expires May 31, 2026 ($312,000/year, Premium managed ops tier).

I had a call with their VP of Engineering (Marcus Webb) last Thursday. Key takeaways:

1. They are happy with the system performance (99.2% uptime, <2s query response). No complaints.
2. Budget pressure: Apex is going through a cost optimization initiative. Marcus asked if we can hold the rate flat or offer a small reduction.
3. Competitive threat: They mentioned that Microsoft Copilot for M365 is being evaluated by their IT team. This is a real risk — Copilot is bundled into their existing M365 license at no marginal cost.

My recommendation:
- Offer a 5% reduction ($296,400/year) in exchange for a 2-year commitment.
- Emphasize that our system is tuned to their specific document corpus (Copilot uses generic models — not fine-tuned on their content).
- Offer to demonstrate accuracy comparison: our system vs. Copilot on their benchmark queries.

Pricing context: per our pricing-sheet.md, 5% discount is within the volume discount policy (>$200K/year) so no special approval needed. A 10% discount would require VP sign-off.

Timeline: Marcus wants a proposal by March 20. I'll draft it this week.

If we lose Apex, that's $312K ARR gone — significant impact on Q2 and beyond. Let's prioritize this.

Let me know if you want to jump on a call before I send the proposal.

Best,
Sales Team
""",
    },
    {
        "subject": "New Remote Work Policy Effective March 15",
        "body": """\
Hi everyone,

I'm writing to share an important update to our Remote Work Policy, effective March 15, 2026.

The updated policy (remote-work-policy.md) has been uploaded to the shared drive. Key changes from the previous version:

1. Core hours clarification: Core hours are now 10 AM – 3 PM in your LOCAL timezone (previously it was ambiguous — some read this as ET). This gives our colleagues in PT and MT timezones more flexibility in the morning.

2. Equipment reimbursement increase: The annual monitor/peripherals cap increases from $400 to $600. Ergonomic chair reimbursement is now available (previously not covered). These changes were approved following the Q1 all-hands survey where 71% of employees cited home office setup as their top benefit request.

3. Security tightened: VPN is now REQUIRED (not recommended) for all access to internal systems. This applies to everyone, including contractors on Project Atlas and Project Beacon. See ai-infrastructure-guide.md for VPN setup instructions (Tailscale).

4. Contractor applicability: Contractors assigned to projects for 3+ months are now covered by the remote work policy for equipment reimbursement purposes. Please note this applies to the contractors onboarding for Project Beacon (starting April 14).

Action items:
- All employees: Please read the updated policy by March 20.
- Managers: Brief your team members on the VPN requirement change at your next 1:1.
- New hires (including Sarah Chen, joining March 10): The $1,500 new hire home office setup reimbursement is available to you from day one.

Please reach out to people@baruchtech.io if you have any questions.

Best,
People Operations
""",
    },
    {
        "subject": "Q1 All-Hands Meeting Notes",
        "body": """\
All-Hands Meeting — Q1 2026
Date: March 4, 2026, 11:00 AM ET
Attendees: All 23 Baruch Technologies employees

AGENDA AND NOTES

1. Q1 Financial Results (Finance Team)
- Revenue: $1,247,500 (14% above Q1 2025, 3% above budget). See q1-2026-financial-report.md for full breakdown.
- Gross margin: 68%. Cash position: $2.1M.
- Highlight: Project Atlas outperformed — $87,500 in additional milestone billings from scope expansion.

2. Project Updates
- Project Atlas (Meridian): Phase 1 accepted January 30. Phase 2 scoping starts April 1.
- Project Beacon (Falcon Ridge): Signed! Kickoff April 14. $165K Phase 1.
- Apex renewal: In negotiation. Decision expected by end of March.
- Northgate Capital: Renewal at risk (-12% QoQ). Marketing doing a case study to support renewal.

3. New Hire Announcement
- Sarah Chen joins March 10 as Senior ML Engineer. She was previously at Scale AI and has 5 years of RAG/embedding systems experience. She'll be on Project Beacon from day one.
- Onboarding buddy: Marcus Johnson. First task: review the architecture docs (project-atlas-architecture.md) and the AI infrastructure guide.

4. Product / Engineering
- GPU cluster is live (A10G x4, AWS us-east-1). See ai-infrastructure-guide.md.
- We had a P2 incident on Feb 28 (47-minute search degradation). Full post-mortem shared in engineering Slack. Root cause was fixed; dimensionality check added to CI.

5. Remote Work Policy Update
- Effective March 15, core hours adjusted, equipment reimbursement increased.
- VPN now required for all internal access. See email from People Ops for details.

6. Q2 Goals
- Revenue target: $1,350,000
- Close Apex renewal by March 31
- Beacon Phase 1 kickoff and first milestone by May 31
- Hire 1 additional senior engineer (JD drafting this week)

NEXT ALL-HANDS: April 7, 2026, 11:00 AM ET

Questions/action items: people@baruchtech.io
""",
    },
    {
        "subject": "Production Incident Post-Mortem - Feb 28",
        "body": """\
INCIDENT POST-MORTEM
Date: February 28, 2026
Severity: P2 (High)
Duration: 47 minutes (14:23 – 15:10 UTC)
Incident Commander: DevOps Lead

SUMMARY

A misconfigured ML pipeline update caused embedding vectors to be generated
with incorrect dimensionality (256 dimensions instead of the expected 768). This
resulted in search quality degradation — queries returned random or irrelevant
results for all users during the incident window.

No data was lost. No personal data was exposed. One client (Project Atlas /
Meridian Corp) was affected; their team was notified per our DPA obligations
(data-processing-agreement.md requires notification within 72 hours of discovery).

TIMELINE

14:23 UTC — Automated integration test fires: "search result count < expected threshold."
14:28 UTC — PagerDuty pages on-call engineer (Jamie Rodriguez).
14:35 UTC — Jamie confirms search quality degradation, opens Slack incident channel.
14:38 UTC — Root cause identified: yesterday's model update changed the embedding dimension.
14:45 UTC — Decision made to roll back to v1.4.2 model (previous good version).
14:55 UTC — Rollback deployed to staging, smoke tests pass.
15:05 UTC — Rollback deployed to production.
15:10 UTC — All metrics back to green. Incident closed.
15:30 UTC — Client notification sent to Meridian IT contact.

ROOT CAUSE

The ML pipeline was updated to use a new embedding model (all-MiniLM-L12-v2, 256d)
without updating the dimension assertion in the CI pipeline. The CI test only
checked that the embedding model loaded successfully, not that the output
dimension matched the production vector store schema (768d for pgvector).

CONTRIBUTING FACTORS

1. No dimension validation in the embedding pipeline tests.
2. Model upgrade PR was not reviewed by a second engineer (reviewer was on PTO).
3. Staging environment uses a small document set — the dimension mismatch was
   not caught because queries still returned results (wrong ones, but results).

ACTION ITEMS

1. [Done] Add dimensionality assertion to all embedding pipeline tests.
2. [In progress] Update staging test suite to run full benchmark queries, not just smoke tests.
3. [Scheduled] Require 2-engineer review for all ML pipeline changes. Update CODEOWNERS file.
4. [Scheduled] Add dimension validation to model registration step in MLflow.

See incident-response-playbook.md for the full on-call and escalation process.

Full incident timeline and logs: https://incidents.baruchtech.io/2026-02-28-p2
""",
    },
    {
        "subject": "ML Pipeline Migration Plan",
        "body": """\
Hi Engineering Team,

Following the Feb 28 incident and the new GPU cluster coming online, we need to
migrate our ML pipeline from the old architecture to the new one. This email
summarizes the plan. Full spec will be in the repo by end of week.

CURRENT STATE

- Embedding: all-MiniLM-L6-v2 (384d), runs on CPU, hosted on ECS Fargate
- Training: Ad-hoc Jupyter notebooks on individual developer machines
- Model registry: manual versioning in S3 (no MLflow)
- Serving: Direct model loading in the application process (no separate serving layer)

TARGET STATE

- Embedding: nomic-embed-text-v1.5 (768d) on the new GPU cluster (see ai-infrastructure-guide.md)
- Training: Standardized job config YAML, submitted via baruch-train CLI
- Model registry: MLflow (deployed on internal K8s) with semantic versioning and approval gates
- Serving: Separate FastAPI embedding service with load balancing (decoupled from app)

MIGRATION PHASES

Phase 1 (March 10–21): Set up MLflow, register current models, establish versioning conventions.
Phase 2 (March 24 – April 4): Migrate training jobs to GPU cluster. Start parallel embedding tests.
Phase 3 (April 7–18): Deploy embedding service as separate pod. A/B test new vs. old embeddings on Project Atlas staging.
Phase 4 (April 21–30): Cutover production to new embedding service. Decommission Fargate tasks.

RISKS

1. Re-embedding cost: Switching from 384d to 768d requires re-indexing all client document corpuses. For Meridian (45K docs), estimated time: 3 hours on 2x A10G GPUs. Schedule during off-hours.
2. Accuracy change: nomic-embed-text-v1.5 benchmarks show 8% improvement on MTEB. But we need to validate on our actual client queries. Benchmark planned for Phase 3.
3. Apex Industries: Their renewal negotiation is ongoing. Do NOT migrate their production environment until renewal is signed (don't risk disruption during commercial negotiations).

Please review and comment by EOD Friday. I'll schedule a 30-min architecture review for next Monday.

Best,
Engineering
""",
    },
    {
        "subject": "Benefits Enrollment Deadline Reminder",
        "body": """\
Hi everyone,

This is a reminder that the 2026 benefits enrollment window closes on March 15, 2026.

If you do NOT take action, your current elections will carry over. However, if you want to make changes — including switching health plans, adding/removing dependents, or enrolling in the FSA/HSA — you must do so before March 15.

HOW TO ENROLL

1. Log in to Rippling: https://app.rippling.com
2. Navigate to Benefits → Open Enrollment 2026
3. Review and confirm your elections
4. Submit before 11:59 PM ET on March 15

2026 PLAN CHANGES

Health: United HealthCare is adding an HDHP + HSA option this year (deductible: $1,500/individual, $3,000/family). The company will contribute $500 to your HSA if you enroll in this plan. The existing Choice Plus PPO continues unchanged.

Dental: Delta Dental is adding orthodontic coverage (50% co-insurance, up to $1,500 lifetime) for adult dependents. This was the #1 requested benefit change in last year's survey.

Vision: No changes.

401(k): The 4% match is unchanged. If you have not yet enrolled in the 401(k) (reminder: immediate vesting), please do so in Rippling — this is separate from benefits enrollment.

NEW HIRES: Sarah Chen (starting March 10) and any other Q1 hires have a 30-day special enrollment window from their start date. You do not need to wait for the annual window.

For questions: people@baruchtech.io or the People Ops Slack channel #people.

Best,
People Operations
""",
    },
    {
        "subject": "New Hire Onboarding - Sarah Chen",
        "body": """\
Hi team,

I'm excited to share that Sarah Chen is joining Baruch Technologies on March 10, 2026 as a Senior ML Engineer. Please give her a warm welcome!

BACKGROUND
Sarah comes to us from Scale AI where she spent 4 years building data annotation pipelines and RAG evaluation frameworks. Before Scale, she was at Hugging Face contributing to the sentence-transformers library. She has deep experience in embedding models, vector databases, and retrieval quality evaluation — exactly what we need for Project Beacon and our ML pipeline migration.

FIRST WEEK PLAN

Day 1 (March 10):
- Equipment setup with IT (laptop + Tailscale VPN — see ai-infrastructure-guide.md)
- HR paperwork and benefits enrollment (benefits-enrollment-deadline email has details; Sarah has 30 days from start date)
- Welcome lunch with the team at 12:30 PM

Week 1 focus:
- Review core architecture docs: project-atlas-architecture.md, ai-infrastructure-guide.md, deployment-runbook.md
- Shadow Sprint 3 standup for Project Atlas (this is winding down, but good context)
- Meet with Engineering Lead on ML pipeline migration plan

Week 2+:
- Fully onboarded to Project Beacon as Tech Lead for the ML components
- Begin Phase 1 architecture review

ONBOARDING BUDDY
Marcus Johnson will be Sarah's onboarding buddy. Marcus, please schedule a 1:1 with Sarah for her first day and check in daily for the first two weeks.

ACCOUNTS TO PROVISION (IT — please action by March 9)
- GitHub (baruch-tech org) — engineer role
- AWS (baruch-dev and baruch-prod profiles)
- Linear, Notion, Slack
- Datadog read access
- MLflow (will need admin access once Phase 1 migration starts)

See employee-handbook.md for the complete new hire checklist.

Welcome, Sarah!

People Ops
""",
    },
    {
        "subject": "Monthly Expense Report Reminder",
        "body": """\
Hi everyone,

Friendly reminder: March expense reports are due by April 5, 2026.

Please submit all February expenses (and any late January expenses) in Expensify before the deadline. Finance processes reimbursements on the 15th of each month — reports submitted after April 5 will be processed in the May cycle.

COMMON MISTAKES TO AVOID

1. Missing project codes: Every expense must be tagged with the correct project code. See expense-policy.md for the full list. Most common:
   - Project Atlas work → P-2024-ATL
   - Project Beacon prep → P-2025-BCN (valid from Feb 1 per pre-sales approval)
   - G&A (non-project) → GA-2026
   - Learning & development → LD-2026

2. Itemized receipts required: Credit card statements are NOT sufficient. We need itemized receipts (hotel folios, restaurant itemized bills, etc.).

3. Meals over $50 (solo): Require manager approval in Expensify before submission. Do not submit unapproved expenses over the limit — they'll be rejected and cause delay.

4. Software subscriptions: If you've signed up for any new software subscriptions (even small ones like $10/month tools), please route through IT for security review and Finance for budget tracking. See expense-policy.md section on software.

GPU CLUSTER EXPENSES
The new GPU cluster costs ($28,500 in March) are being handled directly by Finance via the AWS billing account — do NOT submit these in Expensify. They are already in the Q1 financial report.

Questions: finance@baruchtech.io or #finance on Slack.

Thank you,
Finance Team
""",
    },
    {
        "subject": "Budget Approval for GPU Cluster",
        "body": """\
Hi,

I'm writing to request final budget approval for the GPU cluster purchase discussed in the February engineering planning session.

SUMMARY
- Equipment: 4x AWS g5.xlarge instances (A10G GPU, 24GB VRAM each)
- Commitment: 1-year reserved instances (significant discount vs. on-demand)
- Monthly cost: ~$28,500/month ($342,000/year reserved cost)
- Purpose: Fine-tuning, local embedding model serving, batch inference for clients

BUSINESS CASE

The GPU cluster enables three revenue-generating activities:

1. ML Pipeline Migration (Q1-Q2 2026): Moving our embedding infrastructure from CPU-based Fargate to GPU-accelerated serving. Expected outcome: 40% faster embedding generation, enabling real-time ingestion for Project Beacon's 200K-document corpus.

2. Client Fine-Tuning Services (Q3 2026+): We've had three inbound requests (Apex Industries, two prospects) for custom embedding models fine-tuned on their document corpus. Current pricing spec (pricing-sheet.md) includes a $65,000 service line for this. Requires GPU cluster to be cost-effective.

3. R&D: Testing nomic-embed-text-v1.5 and other open-source models (see ML pipeline migration plan email) before deploying to production.

ROI CALCULATION
Assuming 2 fine-tuning client projects in Q3 2026 at $65K each = $130,000 revenue.
GPU cluster cost for Q1-Q3: $28,500 × 9 months = $256,500.
Marginal GPU cost per project: ~$3,000 (actual GPU time for fine-tuning job).
The cluster also enables the ML pipeline migration which reduces our per-query infrastructure cost.

Break-even: 4 fine-tuning client projects over 12 months.

APPROVAL REQUESTED
Amount: $342,000 annual commitment ($28,500/month)
Budget line: Engineering Infrastructure — Cloud Compute
Approver: CFO + CEO (required per expense-policy.md for purchases >$100K)

Already reflected in Q1 financial report (q1-2026-financial-report.md) as a variance item.

Please confirm approval by March 5 so we can finalize the AWS reserved instance purchase.

Thank you,
Engineering Lead
""",
    },
]


# ---------------------------------------------------------------------------
# OneNote page content definitions
# ---------------------------------------------------------------------------

ONENOTE_PAGES: list[dict] = [
    {
        "title": "Weekly Team Standup - March 3, 2026",
        "html": """\
<!DOCTYPE html>
<html>
<head><title>Weekly Team Standup - March 3, 2026</title></head>
<body>
<h1>Weekly Team Standup - March 3, 2026</h1>
<p><strong>Facilitator:</strong> Engineering Lead &nbsp;&nbsp; <strong>Date:</strong> March 3, 2026 &nbsp;&nbsp; <strong>Duration:</strong> 30 min</p>

<h2>Attendees</h2>
<ul>
<li>Engineering Lead (facilitator)</li>
<li>Jamie Rodriguez (DevOps)</li>
<li>Marcus Johnson (Backend)</li>
<li>Priya Kapoor (ML)</li>
<li>Dev Sharma (Frontend)</li>
<li>Sarah Chen (joining March 10 — introduced via video call)</li>
</ul>

<h2>Project Atlas (Meridian Corp)</h2>
<p><strong>Status:</strong> Green ✓</p>
<ul>
<li>Phase 1 fully accepted Jan 30. Phase 2 scoping call scheduled for April 1.</li>
<li>Meridian IT wants to expand the document corpus to include SharePoint team sites (currently only OneDrive). Marcus estimating 2-week effort. Will add to Phase 2 scope.</li>
<li>P2 incident follow-up (Feb 28): all action items from the post-mortem are in progress. Dimensionality check is live in CI. 2-engineer review requirement for ML changes added to CODEOWNERS.</li>
</ul>

<h2>Project Beacon (Falcon Ridge Financial)</h2>
<p><strong>Status:</strong> Pre-kickoff preparation</p>
<ul>
<li>Kickoff confirmed for April 14. Sarah Chen will be Tech Lead on ML components.</li>
<li>DPA needs to be sent to Falcon Ridge by April 7 — Sales action item.</li>
<li>Architecture: Using same base as Project Atlas (see project-atlas-architecture.md) but with time-indexed search for financial queries. Priya to draft architecture decision record this week.</li>
</ul>

<h2>ML Pipeline Migration</h2>
<p><strong>Status:</strong> Phase 1 starting March 10</p>
<ul>
<li>GPU cluster is live. MLflow deployment target: March 14.</li>
<li>Priya and Sarah (once onboarded) will co-lead the migration.</li>
<li>Risk: DO NOT migrate Apex Industries production until renewal is signed.</li>
</ul>

<h2>Blockers</h2>
<ul>
<li>Need Apex renewal decision before March 31 (renewal-discussion email in progress).</li>
<li>AWS reserved instance approval pending CFO sign-off (budget-approval email sent).</li>
</ul>

<h2>Action Items</h2>
<table border="1">
<tr><th>Owner</th><th>Action</th><th>Due</th></tr>
<tr><td>Marcus</td><td>Draft Phase 2 scope for Meridian SharePoint expansion</td><td>Mar 10</td></tr>
<tr><td>Sales</td><td>Send DPA to Falcon Ridge</td><td>Apr 7</td></tr>
<tr><td>Priya</td><td>ADR: vector DB selection for Beacon (see OneNote research page)</td><td>Mar 10</td></tr>
<tr><td>DevOps (Jamie)</td><td>Deploy MLflow on K8s cluster</td><td>Mar 14</td></tr>
<tr><td>Finance</td><td>Get CFO approval on GPU cluster reserved instances</td><td>Mar 5</td></tr>
</table>

<p><em>Next standup: March 10, 2026</em></p>
</body>
</html>
""",
    },
    {
        "title": "Client Meeting Notes - Meridian Corp",
        "html": """\
<!DOCTYPE html>
<html>
<head><title>Client Meeting Notes - Meridian Corp</title></head>
<body>
<h1>Client Meeting Notes — Meridian Corp</h1>
<p><strong>Meeting Date:</strong> March 2, 2026 &nbsp;&nbsp; <strong>Type:</strong> Phase 2 Pre-Scoping Call</p>
<p><strong>Meridian Attendees:</strong> Katherine Huang (VP Legal Ops), David Park (IT Director), Lisa Novak (Sr. Paralegal)</p>
<p><strong>Baruch Attendees:</strong> Sales Lead, Engineering Lead</p>

<h2>Context</h2>
<p>Project Atlas Phase 1 was accepted January 30, 2026. This call is to discuss Phase 2 scope. See project-atlas-sow.md for Phase 1 deliverables. The system is live and Meridian's 120 legal/compliance staff are actively using it.</p>

<h2>Feedback on Phase 1</h2>
<ul>
<li><strong>Positive:</strong> Search quality is "dramatically better" than their previous system (SharePoint built-in search). Katherine noted that response time is "fast enough that people actually use it."</li>
<li><strong>Pain point:</strong> Users have to log in separately to the Atlas UI; they want SSO from their existing Meridian portal (they use Okta, not just Azure AD). David Park will check if there's an Okta-to-Azure AD SAML federation option.</li>
<li><strong>Feature request:</strong> Lisa Novak: "Can we search by document author or date range?" Currently, the search is content-only. Author and date filters would require metadata indexing. Engineering estimate: 1 week of work — easy win for Phase 2.</li>
</ul>

<h2>Phase 2 Scope Discussion</h2>
<p>Meridian wants to expand the document corpus to include SharePoint team sites (currently only OneDrive is indexed — the Atlas system accesses OneDrive via the same Microsoft Graph API as CodeSight uses for M365 sync).</p>

<ul>
<li>Current corpus: ~45,000 documents (OneDrive)</li>
<li>Proposed addition: ~80,000 documents across 12 SharePoint team sites</li>
<li>Total Phase 2 corpus: ~125,000 documents</li>
</ul>

<p>Additional Phase 2 requests:</p>
<ol>
<li>Date range and author metadata filters on search results</li>
<li>Document upload API (allow legal team to upload external documents for ad-hoc search)</li>
<li>Export search results to PDF with citations</li>
<li>Okta SSO integration (pending David Park's feasibility check)</li>
</ol>

<h2>Commercial Discussion</h2>
<p>Katherine asked for a Phase 2 quote by March 15. Our preliminary estimate:</p>
<ul>
<li>SharePoint team sites expansion: $45,000 (5-week effort)</li>
<li>Metadata filters + export: $25,000 (2-week effort)</li>
<li>Document upload API: $20,000 (1.5-week effort)</li>
<li>Okta SSO: TBD (depends on feasibility; likely $15,000-$25,000)</li>
<li>Estimated Phase 2 total: $90,000-$115,000</li>
</ul>

<h2>Action Items</h2>
<ul>
<li>[Baruch Sales] Send Phase 2 proposal by March 15</li>
<li>[David Park] Confirm Okta feasibility by March 10</li>
<li>[Baruch Engineering] Review SharePoint expansion technical complexity — confirm 5-week estimate</li>
</ul>
</body>
</html>
""",
    },
    {
        "title": "Architecture Decision Record: Vector Database Selection",
        "html": """\
<!DOCTYPE html>
<html>
<head><title>ADR: Vector Database Selection for Project Beacon</title></head>
<body>
<h1>Architecture Decision Record: Vector Database Selection</h1>
<p><strong>ADR Number:</strong> BCN-ADR-001 &nbsp;&nbsp; <strong>Date:</strong> March 3, 2026</p>
<p><strong>Author:</strong> Priya Kapoor &nbsp;&nbsp; <strong>Status:</strong> Proposed (review pending)</p>
<p><strong>Related:</strong> Research on RAG Implementation Patterns (see OneNote page), project-atlas-architecture.md ADR-001</p>

<h2>Context</h2>
<p>Project Beacon (Falcon Ridge Financial, starting April 14) requires a vector database to support semantic search over 200,000 financial research documents. The selection criteria differ from Project Atlas (Meridian) because:</p>
<ol>
<li>Falcon Ridge is a financial services firm with strict data residency requirements (data must stay in AWS us-east-1).</li>
<li>Time-based filtering is critical ("documents from Q3 2024" as a query filter).</li>
<li>The corpus is 4.4× larger than Atlas (200K vs 45K documents).</li>
<li>Future Phase 2 includes real-time Bloomberg data — requires fast ingestion alongside bulk historical data.</li>
</ol>

<h2>Options Considered</h2>
<h3>Option 1: pgvector (PostgreSQL extension)</h3>
<p><strong>Used in:</strong> Project Atlas (production since January 2026)</p>
<p><strong>Pros:</strong></p>
<ul>
<li>Already proven in our stack. Engineering team has operational expertise.</li>
<li>Full SQL expressiveness for metadata filters (date ranges, authors, document types).</li>
<li>Runs on AWS RDS/Aurora — Falcon Ridge's existing cloud provider.</li>
<li>ACID transactions — important for financial data integrity.</li>
</ul>
<p><strong>Cons:</strong></p>
<ul>
<li>At 200K documents × 768 dimensions, the vector index size is ~1.2GB. pgvector HNSW performance degrades somewhat at this scale vs. dedicated vector DBs.</li>
<li>Query latency at scale: ~50-80ms for ANN search at 200K vectors (acceptable for our SLA, but worth monitoring).</li>
</ul>

<h3>Option 2: Qdrant</h3>
<p><strong>Pros:</strong></p>
<ul>
<li>Built for high-dimensional vectors. Consistently faster than pgvector at >100K vectors in benchmarks.</li>
<li>Native payload filtering (equivalent to SQL WHERE clauses) with good performance.</li>
<li>Can be self-hosted on AWS EC2.</li>
</ul>
<p><strong>Cons:</strong></p>
<ul>
<li>New technology for the team. Onboarding time for Sarah Chen and others.</li>
<li>Less mature ecosystem than PostgreSQL.</li>
<li>No ACID transactions — ingestion pipeline must handle idempotency manually.</li>
</ul>

<h3>Option 3: Weaviate</h3>
<p>Eliminated early. Requires Kubernetes operator for self-hosted deployment; Falcon Ridge's AWS setup is ECS-based. Operational complexity not justified.</p>

<h2>Decision</h2>
<p><strong>Recommended: Option 1 (pgvector)</strong></p>
<p>Rationale: At 200K vectors, pgvector HNSW with the right index parameters (m=16, ef_construction=64) delivers acceptable performance (measured at 65ms p95 in local benchmarks). The operational familiarity and SQL metadata filtering outweigh Qdrant's raw performance advantage. We can migrate to Qdrant if Falcon Ridge's corpus grows beyond 1M documents (Phase 3+).</p>
<p>If Phase 3 Bloomberg integration doubles the corpus to 400K+ documents, revisit this decision.</p>

<h2>Consequences</h2>
<ul>
<li>Use Aurora PostgreSQL Serverless v2 on AWS (auto-scaling, no fixed instance costs).</li>
<li>Index parameters: HNSW m=16, ef_construction=64, ef=40 for queries.</li>
<li>Add composite index on (embedding vector, created_date) for time-filtered queries.</li>
<li>Re-evaluate at 6 months post-launch or at 300K+ documents.</li>
</ul>
</body>
</html>
""",
    },
    {
        "title": "Brainstorm: Q2 Product Roadmap",
        "html": """\
<!DOCTYPE html>
<html>
<head><title>Brainstorm: Q2 Product Roadmap</title></head>
<body>
<h1>Brainstorm: Q2 Product Roadmap</h1>
<p><strong>Date:</strong> March 2, 2026 &nbsp;&nbsp; <strong>Participants:</strong> Engineering Lead, PM, Sales Lead</p>
<p><em>Raw brainstorm notes — not finalized. All ideas welcome, no filtering yet.</em></p>

<h2>Theme: "From Search to Insights"</h2>
<p>Project Atlas showed us that customers love the search quality. But the next layer of value is not faster search — it's surfacing insights the user didn't know to look for. Q2 roadmap should push in this direction.</p>

<h2>Feature Ideas (unranked)</h2>

<h3>1. Scheduled Summaries (high confidence)</h3>
<p>Weekly email digest: "Here's what changed in your document library this week." Auto-summarize new/updated documents using Claude. Users define which folders/topics they care about.</p>
<p>Technical complexity: Medium. Requires: change detection (already have delta sync from Microsoft Graph), Claude API call per topic, email delivery (SendGrid).</p>
<p>Revenue angle: Add to Premium managed ops tier. Justifies price increase for Apex renewal.</p>

<h3>2. Cross-Document Contradiction Detection</h3>
<p>Detect when two documents make conflicting claims about the same topic. E.g., two versions of an expense policy with different dollar limits. Legal teams would love this.</p>
<p>Technical complexity: High. Requires: semantic clustering, LLM pairwise comparison. Risk of false positives.</p>
<p>Revenue angle: Meridian Corp would pay for this (Phase 3?). Legal use case is strong.</p>

<h3>3. Query Analytics Dashboard</h3>
<p>Show admins: what are users searching for? Which queries return zero results (content gaps)? Which documents are most referenced in answers?</p>
<p>Technical complexity: Low. Query logs are already stored. Just need a Grafana/Streamlit dashboard.</p>
<p>Revenue angle: Admin dashboard is already in scope (Atlas Phase 1 has basic version). This upgrades it.</p>

<h3>4. Slack Integration</h3>
<p>Allow users to query the document search engine directly from Slack: "@docsearch what is our NDA standard term for non-competes?"</p>
<p>Technical complexity: Low-Medium. We already have Teams bot (bot/ module). Slack would be similar.</p>
<p>Revenue angle: Increases daily active usage. Harder to rip out once embedded in workflows.</p>

<h3>5. Multi-Language Support</h3>
<p>Falcon Ridge Financial has research documents in Spanish, Portuguese, and Mandarin (Latin America and Asia coverage). Current embedding model (nomic-embed-text-v1.5) has multilingual support but we haven't tested it.</p>
<p>Technical complexity: Low (if the model supports it). Need to test and document.</p>

<h3>6. Fine-Tuned Domain Embeddings</h3>
<p>Train a custom embedding model on client's document corpus. Expected 15-20% accuracy improvement over general models on domain-specific queries (financial, legal).</p>
<p>Technical complexity: High. Requires GPU cluster (now available), labeled data (need client annotation), MLflow pipeline.</p>
<p>Revenue angle: Already on pricing sheet ($65K service line). GPU cluster makes this cost-effective.</p>

<h2>Prioritization (first pass)</h2>
<p>Must do Q2: Query Analytics Dashboard (low effort, high visibility), Scheduled Summaries (medium effort, revenue unlock for renewals).</p>
<p>Plan for Q3: Slack Integration, Fine-Tuned Domain Embeddings.</p>
<p>Longer term: Cross-Document Contradiction Detection (needs more design).</p>

<p><em>Next step: PM to formalize into roadmap.md with effort/impact scoring. Engineering review by March 12.</em></p>
</body>
</html>
""",
    },
    {
        "title": "Interview Notes - Senior ML Engineer Candidates",
        "html": """\
<!DOCTYPE html>
<html>
<head><title>Interview Notes - Senior ML Engineer Candidates</title></head>
<body>
<h1>Interview Notes — Senior ML Engineer Candidates</h1>
<p><strong>Role:</strong> Senior ML Engineer &nbsp;&nbsp; <strong>Hiring Manager:</strong> Engineering Lead</p>
<p><strong>Context:</strong> Sarah Chen was selected from this cohort. Notes archived for reference.</p>

<h2>Candidate 1: Sarah Chen</h2>
<p><strong>Date:</strong> February 10, 2026 &nbsp;&nbsp; <strong>Result:</strong> OFFER ACCEPTED — starts March 10</p>

<h3>Background</h3>
<p>5 years experience. Scale AI (4 years): data annotation pipelines, RAG evaluation frameworks. Hugging Face (1 year, open source contributor): sentence-transformers library. MS Computer Science, Stanford.</p>

<h3>Technical Screen Notes</h3>
<ul>
<li><strong>RAG architecture:</strong> Excellent. Immediately identified hybrid BM25+vector as superior to pure vector for document search. Knew about RRF and mentioned k=60 as a common default. Strong signal she's thought deeply about retrieval.</li>
<li><strong>Embedding models:</strong> Deep knowledge. Compared nomic-embed-text-v1.5 vs. text-embedding-3-small on MTEB benchmarks unprompted. Identified that nomic outperforms on domain-specific tasks when fine-tuned.</li>
<li><strong>Systems design:</strong> Designed a scalable ingestion pipeline for 1M documents. Proposed using delta sync (same pattern as our Microsoft Graph connector). Good awareness of incremental indexing vs. full re-index tradeoffs.</li>
<li><strong>ML pipeline:</strong> Strong. Proposed MLflow for model registry, discussed CI validation for embedding dimensionality (ironically, this is exactly what caused our Feb 28 P2 incident — see post-mortem email).</li>
</ul>

<h3>Culture Fit</h3>
<p>Strong. Mentioned "shipping working systems" as the most important thing — aligns with our values. Asked good questions about how we handle client data privacy (reviewed our DPA structure). Interested in the fine-tuning service line (pricing-sheet.md) as a growth area.</p>

<h3>Compensation</h3>
<p>Offered: $185,000 base + 0.4% equity + standard benefits. Accepted without negotiation.</p>

<hr/>

<h2>Candidate 2: Alex Torres</h2>
<p><strong>Date:</strong> February 12, 2026 &nbsp;&nbsp; <strong>Result:</strong> NOT SELECTED</p>

<h3>Strengths</h3>
<p>Strong LLM fine-tuning background (LoRA, QLoRA). Good PyTorch depth. Would have been strong for a pure research role.</p>

<h3>Weaknesses</h3>
<p>Limited production systems experience. When asked about database selection for vector search (similar to our ADR on pgvector vs. Qdrant), gave a generic answer and was unfamiliar with pgvector. Search quality evaluation was shallow — did not mention precision/recall metrics or BEIR/MTEB benchmarks.</p>

<hr/>

<h2>Candidate 3: Neha Gupta</h2>
<p><strong>Date:</strong> February 14, 2026 &nbsp;&nbsp; <strong>Result:</strong> STRONG MAYBE — keep in pipeline for Q3 hire</p>

<h3>Notes</h3>
<p>Excellent infrastructure skills (K8s, AWS, MLflow). Would be ideal for the DevOps/MLOps role we'll need if the ML pipeline migration goes well. Less strong on retrieval research. Reach out when we open the MLOps-focused role in Q3.</p>

<p><em>Hiring process doc: people@baruchtech.io</em></p>
</body>
</html>
""",
    },
    {
        "title": "Research: RAG Implementation Patterns",
        "html": """\
<!DOCTYPE html>
<html>
<head><title>Research: RAG Implementation Patterns</title></head>
<body>
<h1>Research: RAG Implementation Patterns</h1>
<p><strong>Author:</strong> Priya Kapoor &nbsp;&nbsp; <strong>Date:</strong> February 28, 2026</p>
<p><strong>Purpose:</strong> Inform architecture decisions for Project Beacon and the Q2 product roadmap brainstorm.</p>

<h2>Summary</h2>
<p>This note summarizes current best practices in retrieval-augmented generation (RAG) systems, focusing on patterns relevant to document search for enterprise clients (legal, financial, consulting domains). Key finding: hybrid retrieval (BM25 + dense vectors + RRF) remains the gold standard for precision-sensitive enterprise search. New techniques like HyDE and late interaction (ColBERT) show promise but add complexity that may not be justified for our current client scale.</p>

<h2>Retrieval Strategies</h2>

<h3>1. Hybrid BM25 + Dense Retrieval (Current Approach)</h3>
<p>Our current approach in Project Atlas and CodeSight (the internal document search tool — see project-atlas-architecture.md): combine BM25 keyword matching with dense vector search, merge rankings using Reciprocal Rank Fusion (RRF, k=60).</p>
<p><strong>When it works best:</strong> Mixed queries combining exact names/numbers (contract IDs, dates, dollar amounts) with semantic intent. Legal and financial documents are exactly this use case.</p>
<p><strong>MTEB benchmark (our domain):</strong> Hybrid RRF scores ~8-12% higher than pure dense retrieval on financial/legal document benchmarks. Validates our current approach.</p>

<h3>2. HyDE (Hypothetical Document Embeddings)</h3>
<p>Instead of embedding the query directly, use an LLM to generate a hypothetical document that would answer the query, then embed that hypothetical document for retrieval.</p>
<p><strong>Potential benefit:</strong> Better for vague/exploratory queries ("what do our contracts say about liability"). The LLM-expanded query is richer than the raw query.</p>
<p><strong>Cost:</strong> Adds an LLM call to every search query ($0.001-0.003 per query with Claude API). For Falcon Ridge at 5K queries/day, this is $150-450/month additional cost. Probably justified if it meaningfully improves quality.</p>
<p><strong>Recommendation:</strong> A/B test on Project Beacon in Phase 2. Not blocking for Phase 1.</p>

<h3>3. ColBERT / Late Interaction</h3>
<p>Each token in the query interacts with each token in the document (MaxSim scoring) instead of comparing single query vector to single document vector. State-of-the-art on many benchmarks.</p>
<p><strong>Problem:</strong> Storage is proportional to document length × embedding dimensions. For 200K documents at 768d with ColBERT, storage is ~50GB vs ~1.2GB for single-vector approach. Not practical at our scale without specialized infrastructure (Vespa, Weaviate with HNSW+BQ).</p>
<p><strong>Recommendation:</strong> Skip for now. Revisit if client corpus grows to 1M+ documents.</p>

<h2>Chunking Strategies</h2>
<p>Chunking significantly impacts retrieval quality. Key findings from recent papers:</p>
<ul>
<li><strong>Semantic chunking</strong> (split on topic boundaries detected by embedding similarity) outperforms fixed-size sliding window by ~5% on average. Worth implementing for Project Beacon.</li>
<li><strong>Parent-child chunking:</strong> Index small chunks (128 tokens) for precise retrieval, but return the parent chunk (512 tokens) to the LLM for more context. Reduces "out of context" answers.</li>
<li><strong>Context headers</strong> (our current approach): prepending file path + section heading to each chunk before embedding improves retrieval by ~3%. Already implemented in CodeSight.</li>
</ul>

<h2>Evaluation</h2>
<p>Critical gap: we don't have a systematic way to evaluate search quality across client deployments. We rely on client feedback ("it feels better") and ad-hoc benchmark queries.</p>
<p><strong>Recommendation for Q2:</strong> Implement RAGAS or a similar framework to measure:</p>
<ul>
<li>Answer faithfulness (does the answer actually come from the retrieved chunks?)</li>
<li>Context relevance (are the retrieved chunks relevant to the query?)</li>
<li>Answer relevance (does the answer address the query?)</li>
</ul>
<p>This would also make a strong sales differentiator — "here's the measured accuracy on your document corpus" vs. competitors' handwavy claims.</p>

<p><em>Related: Architecture Decision Record for Beacon vector DB selection (separate OneNote page). Q2 roadmap brainstorm notes also in OneNote.</em></p>
</body>
</html>
""",
    },
]


# ---------------------------------------------------------------------------
# OneDrive seeding
# ---------------------------------------------------------------------------


def seed_drive(token: str) -> None:
    client = httpx.Client(timeout=60.0)
    hdrs = headers(token)
    hdrs["Content-Type"] = "text/plain"

    for filename, content in DRIVE_FILES.items():
        url = f"{GRAPH}/me/drive/root:/Documents/Baruch/{filename}:/content"
        print(f"  Uploading {filename} ({len(content)} bytes)...")
        resp = client.put(url, headers=hdrs, content=content.encode("utf-8"))
        if resp.status_code in (200, 201):
            print(f"  -> OK ({resp.status_code})")
        else:
            print(f"  -> ERROR {resp.status_code}: {resp.text[:200]}")
        time.sleep(0.3)  # be polite to the API

    client.close()


# ---------------------------------------------------------------------------
# Mail seeding
# ---------------------------------------------------------------------------


def seed_mail(token: str) -> None:
    client = httpx.Client(timeout=60.0)
    hdrs = headers(token)
    hdrs["Content-Type"] = "application/json"

    for email in EMAILS:
        payload = {
            "message": {
                "subject": email["subject"],
                "body": {
                    "contentType": "Text",
                    "content": email["body"],
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": RECIPIENT,
                        }
                    }
                ],
            },
            "saveToSentItems": "true",
        }
        print(f"  Sending: {email['subject']!r}...")
        resp = client.post(
            f"{GRAPH}/me/sendMail",
            headers=hdrs,
            content=json.dumps(payload).encode("utf-8"),
        )
        if resp.status_code == 202:
            print(f"  -> Sent (202)")
        else:
            print(f"  -> ERROR {resp.status_code}: {resp.text[:200]}")
        time.sleep(0.5)

    client.close()


# ---------------------------------------------------------------------------
# OneNote seeding
# ---------------------------------------------------------------------------


def seed_notes(token: str) -> None:
    client = httpx.Client(timeout=60.0)
    hdrs = headers(token)
    json_hdrs = {**hdrs, "Content-Type": "application/json"}

    # Step 1: Create (or find) the "Baruch Notes" notebook
    print("  Creating notebook 'Baruch Notes'...")
    resp = client.post(
        f"{GRAPH}/me/onenote/notebooks",
        headers=json_hdrs,
        content=json.dumps({"displayName": "Baruch Notes"}).encode("utf-8"),
    )
    if resp.status_code in (200, 201):
        notebook_id = resp.json()["id"]
        print(f"  -> Created notebook: {notebook_id}")
    elif resp.status_code == 409:
        # Already exists — find it
        print("  -> Notebook already exists, looking it up...")
        list_resp = client.get(f"{GRAPH}/me/onenote/notebooks", headers=hdrs)
        notebooks = list_resp.json().get("value", [])
        notebook_id = next(
            (nb["id"] for nb in notebooks if nb.get("displayName") == "Baruch Notes"),
            None,
        )
        if not notebook_id:
            print("  -> ERROR: Could not find existing 'Baruch Notes' notebook.")
            client.close()
            return
        print(f"  -> Found notebook: {notebook_id}")
    else:
        print(f"  -> ERROR creating notebook {resp.status_code}: {resp.text[:200]}")
        client.close()
        return

    # Step 2: Get (or create) a default section
    time.sleep(1.0)
    print("  Fetching sections...")
    resp = client.get(
        f"{GRAPH}/me/onenote/notebooks/{notebook_id}/sections", headers=hdrs
    )
    sections = resp.json().get("value", [])

    if sections:
        section_id = sections[0]["id"]
        print(f"  -> Using section: {sections[0].get('displayName')} ({section_id})")
    else:
        # Create a default section
        print("  Creating default section 'General'...")
        resp = client.post(
            f"{GRAPH}/me/onenote/notebooks/{notebook_id}/sections",
            headers=json_hdrs,
            content=json.dumps({"displayName": "General"}).encode("utf-8"),
        )
        if resp.status_code in (200, 201):
            section_id = resp.json()["id"]
            print(f"  -> Created section: {section_id}")
        else:
            print(f"  -> ERROR creating section {resp.status_code}: {resp.text[:200]}")
            client.close()
            return

    # Step 3: Create each page
    page_url = f"{GRAPH}/me/onenote/sections/{section_id}/pages"
    html_hdrs = {**hdrs, "Content-Type": "text/html"}

    for page in ONENOTE_PAGES:
        print(f"  Creating page: {page['title']!r}...")
        resp = client.post(
            page_url,
            headers=html_hdrs,
            content=page["html"].encode("utf-8"),
        )
        if resp.status_code in (200, 201):
            print(f"  -> Created ({resp.status_code})")
        else:
            print(f"  -> ERROR {resp.status_code}: {resp.text[:200]}")
        time.sleep(0.5)

    client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("Authenticating with Microsoft 365...")
    print(
        "(If this is the first run, you will be prompted to complete device-code login.)"
    )
    token = get_token()
    print("Authentication successful.\n")

    print("=" * 60)
    print("Seeding OneDrive (15 files -> /Documents/Baruch/)...")
    print("=" * 60)
    seed_drive(token)

    print()
    print("=" * 60)
    print("Seeding Outlook (12 emails -> self)...")
    print("=" * 60)
    seed_mail(token)

    print()
    print("=" * 60)
    print("Seeding OneNote (notebook + 6 pages)...")
    print("=" * 60)
    seed_notes(token)

    print()
    print("=" * 60)
    print("Done! All content seeded.")
    print()
    print("To sync and index the new content, run:")
    print("  python -m codesight sync --source m365")
    print("=" * 60)


if __name__ == "__main__":
    main()
