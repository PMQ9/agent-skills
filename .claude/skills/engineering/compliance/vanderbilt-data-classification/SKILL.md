---
name: vanderbilt-data-classification
description: Apply Vanderbilt University's L1–L4 data classification scheme to any code, data flow, prompt, log, or vendor integration that touches institutional data. Trigger when the work involves student/HR/finance/research/health/donor/payment data, when deciding which generative-AI tool may receive a given dataset (ChatGPT Edu vs Amplify vs Microsoft Copilot vs none), when masking/redacting before an LLM call, when labeling files in OneDrive/SharePoint/Teams, when planning a vendor integration that exports data, or when reviewing a guardrail. Trigger even if the user does not say "L3" or "classification" — phrases like "send roster to OpenAI," "log this prompt," "export to a SaaS tool," "auto-label this file," or "prompt the model with the donor list" all need this skill.
---

# Vanderbilt Data Classification (L1–L4) and AI Guardrails

This skill encodes Vanderbilt's data classification framework and the approved-tool matrix for sending data to generative AI. The classification scheme is institutional policy — it is not derivable from the codebase, and getting it wrong creates legal/regulatory liability (FERPA, HIPAA, GLBA, PCI, ITAR/EAR, CJIS), not just engineering rework.

This is not legal advice. When you cannot map a piece of data to a level, or you are about to open a new outbound data path, escalate to the **Office of Cybersecurity** (`cybersecurity@vanderbilt.edu`) and the relevant data steward (registrar for student data, HR for employee data, OCGA/sponsored programs for research, etc.) before shipping. Sources at the bottom of this skill — read them when policy details matter.

## The four levels

Vanderbilt's scheme is a four-tier ladder. Each level inherits the controls of the levels below it, plus its own. When in doubt, classify *up*.

### L1 — Public
- **Definition:** Intended for public release.
- **Examples:** Course catalogs, marketing material, press releases, FERPA-defined directory info *for students who have not opted out*, job postings, published research.
- **Storage:** Anywhere.
- **AI:** Any tool, including consumer ChatGPT/Claude/Gemini accounts.
- **Watch-out:** "Directory info" stops being L1 the moment a student has a FERPA block — it becomes L3. See `ferpa-compliance` for the opt-out trap.

### L2 — Institutional Use Only
- **Definition:** Private to VU; should not be shared externally without permission.
- **Examples:** Non-public contracts, budgets, blueprints, internal procedures, calendars, performance data, *unpublished* research, aggregated/de-identified data, surveys.
- **Storage:** Vanderbilt-owned IT assets.
- **AI:** ChatGPT Edu, Amplify, Microsoft Copilot — sanctioned. Not consumer/personal AI accounts.

### L3 — Restricted
- **Definition:** Confidential by law or contract, or otherwise should not be shared with unauthorized persons.
- **Examples:** Passwords/access secrets, donor information, NDAs, **PII**, **FERPA-protected education records**, **research health information (RHI)**, **GDPR personal data**, **Data Use Agreement (DUA) data**, advising notes, transcripts, grades, financial aid records (non-GLBA-regulated portions), application materials.
- **Storage:** VUIT-issued workstations or VUIT-managed services only — OneDrive, SharePoint, Teams, Box, Vanderbilt Azure, Vanderbilt AWS. Encryption required.
- **AI:** Amplify and Microsoft Copilot only — and **only L3 that is not also a regulated dataset**. ChatGPT Edu is **not** approved for L3.
- **Sharing:** Existing guests only. No external user access.

### L4 — Critical
- **Definition:** Confidential by law/contract **and** requires bespoke security beyond standard controls.
- **Examples:** **PCI** (cardholder data), **GLBA-regulated student financial aid information**, **CUI** (Controlled Unclassified Information), **export-controlled** information (ITAR/EAR), **CJIS** law enforcement records, **HIPAA PHI** (treated at this tier for AI purposes — see below), **federal tax information (FTI)**.
- **Storage:** Bespoke. Contact the Office of Cybersecurity for an approved environment before any storage decision.
- **AI:** **No Vanderbilt-sanctioned generative AI tool is approved for L4 data.** Including Amplify. Including Copilot. Stop and escalate.
- **Sharing:** Vanderbilt-only, with content marking required (header *and* content).

> Note on the policy text: the public Cybersecurity Guidelines page (current) treats PCI, GLBA, CUI, export-controlled, and CJIS as **L4**. The 2020 Data Classification Policy PDF lists some of these (e.g. payment card information, FTI, export-controlled) under L3 categories. **Follow the current Cybersecurity guidance**, which is more protective. If you encounter an authoritative-looking citation pointing the other way, flag it for the user and confirm with `cybersecurity@vanderbilt.edu`.

## The AI tool × data level matrix

This is the operational rule. Memorize it.

| Tool | L1 Public | L2 Institutional | L3 Restricted | L4 Critical |
|---|---|---|---|---|
| **ChatGPT Edu** (Vanderbilt SSO) | ✅ | ✅ | ❌ | ❌ |
| **Amplify** (Vanderbilt-built) | ✅ | ✅ | ✅ *(except regulated datasets)* | ❌ |
| **Microsoft Copilot** (campus) | ✅ | ✅ | ✅ *(except regulated datasets)* | ❌ |
| Personal/consumer ChatGPT, Claude.ai, Gemini, etc. | ✅ | ❌ | ❌ | ❌ |
| Any other unvetted SaaS LLM | ❌ | ❌ | ❌ | ❌ |

Two things this table does *not* say but you must know:

1. **"Regulated dataset" excludes more than the L4 categories.** FERPA records and HIPAA PHI are L3-tier in the abstract, but Vanderbilt's generative-AI guidance prohibits regulated data even from Amplify and Copilot. **Don't put PHI, FERPA records, or financial-aid information into any generative AI tool, even an approved one, without explicit sign-off from Cybersecurity and the relevant data steward.** Amplify's own pilot documentation explicitly excludes PHI.
2. **The matrix says nothing about ownership.** Per Vanderbilt HR's generative AI policy, do not use any AI tool — sanctioned or not — when the university *must* own the final work product, because copyright ownership of model outputs is unsettled.

## Mental model: classify the data, then choose the tool

When code touches data and an AI call is in the picture, run this in order:

1. **Classify the data.** What's the highest level present? If a record contains both L2 and L3 fields, the whole thing is L3. If unsure, classify *up*.
2. **Identify regulated overlays.** Is this FERPA? HIPAA? GLBA? PCI? Export-controlled? Regulated overlays restrict tools further than the level number alone.
3. **Pick the tool.** From the matrix above. If the matrix says ❌ for the data + tool combination, stop — do not "just redact a few fields and proceed" without a documented redaction plan reviewed by Cybersecurity.
4. **Log the disclosure.** Sending data to an AI vendor is a disclosure under FERPA § 99.32 and analogous regimes. See `audit-logging` and `ferpa-compliance`. The log entry is required even when the tool is approved.

```python
# Sketch — do NOT use as-is; the policy lookup must come from a
# config/service that the data-stewardship team controls, not hardcoded.
def can_send_to_tool(record_classification: Level, tool: AITool) -> bool:
    if record_classification == Level.L4:
        return False  # No sanctioned tool approved for L4
    if record_classification == Level.L3:
        if tool not in (AITool.AMPLIFY, AITool.COPILOT):
            return False
        if record_has_regulated_overlay(record):  # FERPA, HIPAA, GLBA, PCI, ...
            return False
    if record_classification == Level.L2:
        return tool in (AITool.AMPLIFY, AITool.COPILOT, AITool.CHATGPT_EDU)
    return True  # L1
```

## Masking and redaction before an AI call

If the only way to use AI on a record is to first remove the sensitive fields, treat redaction as a **classification-lowering operation** that must be deliberate, reviewed, and verifiable.

- **Whitelist, don't blacklist.** Build the prompt from explicitly chosen fields, not from "the record minus the bad ones." Schema drift adds new fields silently; blacklists rot.
- **Deterministic redaction over heuristic.** Regex-based PII scrubbers miss things. Prefer dropping the field entirely or replacing it with a stable token (`<STUDENT_ID>`) and re-attaching the value after the call.
- **Quasi-identifiers are real identifiers.** A 5-digit ZIP + birth date + sex re-identifies most U.S. residents. The HIPAA Safe Harbor 18 identifiers list (in the 2020 policy doc) is the floor, not the ceiling. See `pii-handling`.
- **Free-text fields leak.** An advising note, a support ticket body, an email subject — these contain L3 data even when the structured columns look L2. Don't classify by table; classify by *contents*.
- **Document the redaction.** A code comment is not enough. Cite the data steward who approved the field selection in a `DATA_FLOWS.md` or equivalent that survives refactors.

If you find yourself building "PII redaction" to push L3 data through an L2-only tool, you are taking on substantial risk. Stop and escalate.

## File labeling in Microsoft 365

Vanderbilt's M365 sensitivity labels map directly to the four levels. When code generates documents in OneDrive/SharePoint/Teams, it should set the label, not leave it to the user.

| Label | Encryption | Offline access | Content marking | External sharing |
|---|---|---|---|---|
| Public (L1) | No | Always | No | Anyone |
| Institutional Use Only (L2) | No | 30 days | No | Existing guests |
| Restricted (L3) | Yes | Never | Header only | Existing guests |
| Critical (L4) | Yes | Never | Header + content | Vanderbilt only |

Note: PowerBI and Tableau cannot read L3/L4 labeled files because of the encryption controls. Plan analytics pipelines accordingly — the analytics platform itself must be VUIT-managed and the data steward must approve its access path.

## Logs, caches, and side channels

Classification follows the data, not the channel. Common leakage paths to audit:

- **Application logs.** A log line that prints a request body containing a SSN is now an L3+ artifact, regardless of the log destination.
- **Error tracking (Sentry/Rollbar).** Stack-trace local variables capture whatever was in scope. Either scrub at the SDK level or don't send error data from L3+ code paths to a non-VUIT-approved tool.
- **Caches and queues.** Redis, SQS, Kafka — the bytes resting in the cache are classified the same as the source.
- **Analytics events.** A `track("viewed_grade", { student_id, grade })` event ships L3 to whatever analytics vendor — usually unapproved for L3.
- **AI prompt caches.** Any `cache_control` or response cache that stores prompts is now storing whatever data went into them. Same classification as the inputs.

The default question to ask: *if a copy of this byte ended up at the vendor, would I be comfortable with that under the matrix above?*

## Vanderbilt data domains

The university organizes data into 16 domains (Student, Faculty, Staff, Employment, Alumni/Parents/Prospects, Athletics, Sponsored Programs, Finance, Campus Services, Facilities, Library & Collections, Marketing & Communications, Government & Community, Legal & Compliance, Technology, Research). Each has a data steward; the steward is the person who can answer "what level is this field?" and "may we send it to vendor X?". Most domain detail pages are internal-only — get the steward contact from the data domain owner directly, don't guess.

## Peer-institution reference points

Vanderbilt's policy is the authoritative one. These are reference points for problems Vanderbilt's published guidance does not yet address (use them to inform a question to Cybersecurity, not to make unilateral calls):

- **Harvard / HMS IT** publishes an explicit AI tool × data level matrix: Level 3 and below for AI Sandbox / ChatGPT Edu / Adobe Firefly / HUIT API Portal; Level 4 for HMS Azure AI or Longwood Cluster only, with prior approval; "*Avoid entering confidential information (Level 2 and above) into public-facing AI platforms.*" PHI is not approved for any public AI tool — only the dedicated HMS Azure AI / Longwood paths. This is a useful precedent if Vanderbilt has not yet sanctioned a path for a particular L4/PHI workflow.
- **Stanford** requires Stanford-approved tools for most prompts/materials and prohibits inputting "information that should not be made public, including personal or confidential information and proprietary or copyrighted materials." Useful framing when explaining to non-engineers why redaction-and-send-to-public-LLM is not an answer.
- **Many peer R1s** (BU, Columbia, Duke, UT Austin, UIC) use a four-tier scheme with the boundaries (Public / Internal / Confidential / Restricted) drawn close to Vanderbilt's. The terms "Confidential" and "Restricted" are used in opposite orders at different schools — when reading a peer policy, anchor on the *examples*, not the *labels*.

If Vanderbilt's published guidance is silent on a workflow you need (e.g., "may I use an OpenAI batch endpoint for de-identified L3 research data?"), the answer is "ask Cybersecurity," not "borrow Harvard's answer." Use the peer policy to draft the question, not the answer.

## Code-review checklist

For any PR that touches institutional data, walk this list:

- What classification level is the highest-classified field in this code path? (If you cannot answer, stop.)
- Are there regulated overlays (FERPA, HIPAA, GLBA, PCI, ITAR/EAR, CJIS)?
- Where does the data go? Application log? External vendor? AI tool? Cache? Email? Webhook?
- For each outbound destination: is that destination approved for this level *and* this regulated overlay?
- For AI calls: does the tool match the matrix? Is the call logged as a disclosure?
- For redaction-before-send paths: is the field selection a whitelist? Is the redaction documented and signed off by a steward?
- For new vendors: has the contract / DPA / BAA been reviewed? (Engineering doesn't decide this — procurement and Cybersecurity do.)
- For file output to M365: is the sensitivity label being applied programmatically?

## When to escalate

Stop and contact `cybersecurity@vanderbilt.edu` (and the relevant data steward) before merging when:

- Any L4 data is in scope.
- Any regulated overlay (FERPA, HIPAA, GLBA, PCI, ITAR/EAR, CJIS) is in scope and the destination isn't already documented as approved for that overlay.
- A new vendor or AI tool is being introduced into the data path.
- A redaction step is the only thing standing between an L3 dataset and a non-L3 destination.
- The user is asking you to classify the data and the right answer is genuinely unclear — don't guess.

## Cross-references in this library

- `ferpa-compliance` — student-record specifics, consent exceptions, FERPA-block flag, § 99.32 disclosure logging.
- `pii-handling` — PII lifecycle, quasi-identifiers, de-identification, redaction patterns.
- `audit-logging` — disclosure logs, who-did-what-when, tamper-evident retention.
- `authn-authz` — role-based access enforcement that backs L3+ "specific personnel" rules.
- `prompt-injection-defense` — when untrusted input flows into an AI call, classification + injection defense both apply.
- `llm-application-engineering` — caching, retries, observability — all of which need to honor classification.
- `amplify-platform` — engineering details for the Vanderbilt-approved Amplify environment.

## Sources (verify against current versions before relying)

- Vanderbilt Office of Cybersecurity — Data Classification Guidance: <https://www.vanderbilt.edu/cybersecurity/guidelines/data-classification/>
- Vanderbilt Office of Cybersecurity — Generative AI Guidance: <https://www.vanderbilt.edu/cybersecurity/guidelines/generativeai/>
- Vanderbilt Office of Cybersecurity — Data Labeling in Microsoft Tools: <https://www.vanderbilt.edu/cybersecurity/guidelines/data-labeling/>
- Vanderbilt Data Classification Policy (May 2020 PDF): <https://cdn.vanderbilt.edu/vu-URL/wp-content/uploads/sites/352/2021/03/19225810/Data-Classification-Policy-05.11.2020.pdf>
- Vanderbilt HR — Generative AI policy for staff: <https://hr.vanderbilt.edu/policies/generative-ai/>
- Vanderbilt — Generative AI tools: <https://www.vanderbilt.edu/generative-ai/tools/>
- Vanderbilt — Amplify platform: <https://www.vanderbilt.edu/generative-ai/custom-software-pilot-amplify/>
- Vanderbilt News — Multi-tool AI strategy (Jan 2026): <https://news.vanderbilt.edu/2026/01/12/vanderbilt-expands-multi-tool-ai-strategy-with-chatgpt-edu-amplify-2-0-and-more/>
- Vanderbilt — Data Domains: <https://www.vanderbilt.edu/data/data-domains/>
- Harvard HMS IT — Generative AI: <https://it.hms.harvard.edu/about/policies-and-guidelines/generative-ai>
- Harvard Provost — Generative AI guidelines: <https://provost.harvard.edu/guidelines-using-chatgpt-and-other-generative-ai-tools-harvard>
- Stanford — Generative AI policy guidance: <https://communitystandards.stanford.edu/generative-ai-policy-guidance>
