---
name: hipaa-compliance
description: Use this skill for any work touching protected health information (PHI), electronic protected health information (ePHI), patient records, clinical data, healthcare provider workflows, or systems integrating with EHRs (Epic, Cerner/Oracle Health, Athena, Meditech). Trigger when the user mentions HIPAA, HITECH, the Privacy Rule, the Security Rule, the Breach Notification Rule, the 2025 Security Rule update, business associate agreements (BAAs), minimum necessary, the 18 HIPAA identifiers, de-identification (Safe Harbor or Expert Determination), Vanderbilt University Medical Center (VUMC) data, clinical research data under a covered entity, FHIR/HL7 with patient data, sending PHI to an LLM, audit logs for PHI access, encryption requirements, breach notification timelines, or designing any system that stores, transmits, or processes patient data.
---

# HIPAA Compliance

HIPAA is the floor for handling patient data in the United States, not the ceiling. The cost of a HIPAA violation is real (civil penalties tier from $137 to $2.13M per violation category per year as of 2025; criminal penalties for willful neglect; OCR enforcement actions become public). The cost of designing for HIPAA from day one is small. The cost of retrofitting it onto an existing system is enormous and rarely complete.

This skill covers what an engineer needs to know to build, modify, or review systems that handle PHI. It is not legal advice. **For any actual compliance decision, route through your organization's HIPAA Privacy Officer, Security Officer, and counsel.** At Vanderbilt, that's VUMC Privacy Office and VUMC Information Security; the university side defers to them for clinical data.

## What HIPAA covers, in one paragraph

HIPAA applies to **covered entities** (health plans, healthcare clearinghouses, healthcare providers who transmit health information electronically) and to **business associates** (vendors and contractors who handle PHI on behalf of a covered entity). It governs **protected health information** — individually identifiable health information held or transmitted by a covered entity or business associate, in any form. The **Privacy Rule** governs uses and disclosures. The **Security Rule** governs administrative, physical, and technical safeguards for ePHI specifically. The **Breach Notification Rule** governs what happens when something goes wrong.

Note: HIPAA does **not** cover all health data. A consumer fitness tracker, a wellness app you bought as an individual, or genetic data sent to 23andMe is not under HIPAA — it's a different regulatory landscape (state privacy laws, FTC, sometimes nothing). The trigger is "covered entity or business associate handling identifiable health info," not "data is health-related."

## The 18 HIPAA identifiers (Safe Harbor)

Removing all 18 is one of two paths to **de-identification**, after which data is no longer PHI:

1. Names
2. Geographic subdivisions smaller than a state (street, city, county, ZIP — the first 3 digits of ZIP can be retained if the population in that ZIP3 is > 20,000)
3. All elements of dates (except year) related to an individual — birth date, admission, discharge, death; ages over 89 must be aggregated into "90+"
4. Phone numbers
5. Fax numbers
6. Email addresses
7. Social Security numbers
8. Medical record numbers
9. Health plan beneficiary numbers
10. Account numbers
11. Certificate/license numbers
12. Vehicle identifiers and serial numbers (VIN, license plate)
13. Device identifiers and serial numbers
14. URLs
15. IP addresses
16. Biometric identifiers (fingerprints, voice prints)
17. Full-face photographs and comparable images
18. Any other unique identifying number, characteristic, or code

Plus the catch-all: no actual knowledge that the remaining info could identify the individual.

The other path is **Expert Determination** — a qualified statistician determines re-identification risk is "very small." More flexible (you can keep some dates and granular geography), more expensive, requires written documentation.

**De-identified data is not PHI.** Use this. If your analytics warehouse only needs population-level stats, de-identify before it lands there. The downstream blast radius collapses.

The middle ground is a **Limited Data Set** — strips most identifiers but allows dates and city/state/ZIP. Permitted for research, public health, healthcare operations under a Data Use Agreement (DUA). Still PHI, but with looser sharing rules than full PHI.

## The Security Rule: technical safeguards for ePHI

The 2025 update (HHS proposed in late 2024, finalized 2025) tightened many requirements that were previously "addressable" into "required." Key technical safeguards as they stand:

| Safeguard | Practical implementation |
|---|---|
| **Access control** | Unique user IDs (no shared accounts), automatic logoff, emergency access procedure, role-based access. |
| **Audit controls** | Log access to ePHI. Retain logs. Review them. (See `audit-logging`.) |
| **Integrity** | Mechanisms to detect ePHI alteration or destruction. Hash, signed audit trails. |
| **Authentication** | Verify identity before access. **MFA required** under the 2025 update for most ePHI access. |
| **Transmission security** | Encryption in transit. TLS 1.2+ at minimum, TLS 1.3 preferred. Was "addressable," now required. |
| **Encryption at rest** | Required under 2025 update. Was "addressable" before. |

Practically, what that means for a system handling ePHI in 2026:

- **TLS 1.2+ on every wire**, no exceptions. TLS 1.3 strongly preferred. No mixed-content. No HTTP redirects to HTTPS that allow MITM downgrade — HSTS preloaded.
- **Encryption at rest** on every storage layer: database storage encryption (RDS/Aurora/Azure SQL with TDE), S3/Blob with SSE-KMS, EBS/managed disks encrypted, backups encrypted, replicas encrypted.
- **Customer-managed keys (CMK)** in KMS with rotation, audit, and break-glass procedures. AWS-managed keys are technically encrypted-at-rest but offer less control.
- **MFA on all access to systems containing ePHI** — admin consoles, application logins for clinical users, API keys (or service accounts via OIDC/workload identity, not long-lived credentials), VPN, jump hosts.
- **Unique user IDs.** No shared `clinic_admin` accounts. Federated identity (SAML/OIDC) preferred so that disabling someone in one place disables everywhere.
- **Automatic logoff** — sessions expire after inactivity. The Security Rule doesn't specify a duration; clinical context typically uses 15-30 minutes.
- **Comprehensive audit logging** of who accessed what when. See the `audit-logging` skill for how; the HIPAA-specific add is that audit logs are reviewed (not just stored), and retention is generally 6 years to align with HIPAA documentation retention.

## Business Associate Agreements (BAAs)

Any vendor that touches PHI on behalf of a covered entity needs a BAA. No BAA, no PHI. This applies to:

- Cloud providers (AWS, Azure, GCP — all have BAAs for specified services).
- LLM providers (OpenAI offers a BAA on enterprise tiers; Anthropic has BAAs available; Google Cloud Vertex AI has one for Google's models). Consumer ChatGPT does not have a BAA.
- Email providers, SMS gateways, analytics, error trackers (Sentry, Datadog have BAAs available).
- Backup vendors, log aggregators, monitoring platforms.
- Any SaaS your application uses to process or store PHI.

Critical point: **a BAA does not automatically extend to all of a vendor's services.** AWS has a list of "HIPAA Eligible Services." Azure has "covered services." Using a service that isn't on the list with PHI violates the BAA, even if the rest of your account is fine. Check the list. Match it to your architecture.

The corollary: **subprocessors**. Your vendor's vendors. The BAA must flow down. Most well-known vendors do this; small SaaS vendors often don't, and "we have AWS underneath" doesn't mean their use of AWS is BAA-covered.

## Minimum necessary

The Privacy Rule requires that PHI use and disclosure be limited to the minimum necessary to accomplish the purpose. Engineering implications:

- **Don't return more than the caller needs.** A doctor's portal needs medication list; the billing system doesn't need the full clinical note. Field-level access control, not just record-level.
- **Don't log fields you don't need for the audit log.** Logging the full request body of a clinical API is a great way to put PHI in your log aggregator.
- **Default to redaction for downstream systems.** Errors shipped to Sentry should be PHI-free by default — strip request bodies, scrub URLs (path parameters often contain MRNs).
- **Reports and exports** — design with field selection rather than "everything about this patient."

Treatment, payment, and healthcare operations (TPO) are exceptions where minimum necessary doesn't strictly apply within those workflows — but it still applies for the *purpose* you're sharing for.

## Patient rights (Privacy Rule)

Patients have, among others:

- **Right to access** their own records (45 CFR 164.524). Generally within 30 days. Electronic format if they ask. The cost may only be reasonable cost-based.
- **Right to amendment** (164.526) — request corrections.
- **Right to accounting of disclosures** (164.528) — list of who you disclosed their PHI to outside TPO, going back 6 years.
- **Right to restrict** disclosures, including a hard right to restrict disclosure to a health plan when the patient pays out of pocket in full.
- **Right to confidential communications** — communicate at alternate addresses/numbers.
- **Right to be notified of breaches.**

System implications:

- **The accounting of disclosures requires logging** every disclosure outside TPO, with date, recipient, purpose, and brief description. This is a specific log shape, not a general audit log.
- **The right to access requires extractability.** A patient can ask for their data; you must be able to produce it. If your data model can't reconstruct a single patient's record, that's a HIPAA-relevant gap.
- **Amendments require versioning.** Original record stays; amendment is added.

## Breach Notification Rule

A breach is, broadly, an unauthorized acquisition, access, use, or disclosure of unsecured PHI that compromises the security or privacy of the PHI. ("Unsecured" basically means not encrypted to NIST standards or destroyed.)

Notification timelines:

- **Affected individuals**: without unreasonable delay, no later than **60 days** from discovery.
- **HHS**: with the individual notice if breach affects ≥ 500 individuals; otherwise annually for smaller breaches.
- **Media**: prominent media outlet for breaches affecting ≥ 500 in a state/jurisdiction.
- **Business associate to covered entity**: without unreasonable delay, **no later than 60 days** from discovery (often the BAA contractually requires faster — 30 days is common, sometimes 24-72 hours for the initial notice).

There is a **safe harbor** for properly encrypted ePHI: if PHI is encrypted to NIST standards (FIPS-validated), a loss of the encrypted blob (lost laptop, stolen backup tape) is generally **not a breach**. This is the practical reason to encrypt at rest universally — it converts "we lost a laptop with patient records, now do notification" into "we lost a laptop, no breach."

What engineers should do during an incident:

- **Preserve evidence.** Don't wipe machines, don't rotate logs prematurely. Snapshot, isolate, hand off to the security team.
- **Don't notify on your own.** Notification decisions go through the Privacy Officer and counsel. Engineers report up immediately; they do not contact patients or media.
- **Document everything contemporaneously.** What you knew, when, what you did, when. This is what determines "without unreasonable delay."

## Sending PHI to LLMs

A live and rapidly evolving area, and a place where engineers most often accidentally leak PHI.

**Default rule: no PHI to LLMs without a BAA in place for that specific service.**

Practical landscape (verify current state with your privacy office before relying on this):

- **Anthropic Claude** — BAAs are available for Claude API usage and Amazon Bedrock / Vertex AI deployments. Verify your contract covers it.
- **OpenAI** — BAAs available on enterprise/business tiers (ChatGPT Enterprise, API with Zero Data Retention agreement). Consumer ChatGPT does not have a BAA.
- **Azure OpenAI Service** — covered under Azure's BAA when configured per Microsoft's HIPAA guidance.
- **AWS Bedrock** — HIPAA-eligible, models available under the BAA vary by region and model.
- **Google Vertex AI** — covered for Google's first-party models (Gemini) under Google Cloud's BAA.
- **Local / self-hosted models** (Llama, Mistral, etc., on your own infra) — no third party involved, so no BAA needed for the model itself; the underlying compute still needs to be a HIPAA-covered service.

For Vanderbilt specifically: route all PHI-AI questions through VUMC Information Security and Privacy. **Amplify** (the institution's GenAI platform) is one of the approved channels with appropriate agreements; consumer tools (free ChatGPT, Claude.ai consumer tier) are not. The `vanderbilt-data-classification` skill has the up-to-date matrix.

When PHI does go to an approved LLM, additional engineering practices:

- **Minimize**. Don't pass the full chart when you need the medication list.
- **Mask what you can**. Names, MRNs, SSNs replaced with stable tokens — `<PATIENT_NAME>`, `<MRN>` — and resolved client-side. Keeps the PHI off the LLM's logs entirely.
- **Disable training**. Most enterprise contracts already do, but verify. ZDR (zero data retention) is even better when available.
- **Don't put PHI in system prompts that get cached or shared across users.**
- **Audit log every PHI-bearing prompt** the same way you audit any other PHI access — who asked, what they asked, what came back, when.
- **Output validation**. The model can hallucinate; treat clinical content output as needing human review before action.

## Common engineering scenarios

### "We need to ship logs to a SaaS log aggregator"

PHI in logs is the most common HIPAA leak. Path:

1. BAA with the aggregator (Datadog, Splunk Cloud, New Relic — all have BAAs). Verify.
2. Strip PHI before logging. Application-level redaction in the logger config (Pino redaction, Python `logging` filter, structlog processor). Fields like `request.body`, URL paths with patient IDs, `user.email` should be allow-listed, not blocked-listed.
3. Treat the URL as PHI-bearing — a URL like `/patients/12345/notes` discloses an MRN.
4. Encrypt in transit. The aggregator's BAA presumes TLS to their endpoint.

### "We're integrating with an EHR via FHIR"

- TLS 1.2+ to the FHIR endpoint, mutual TLS in many integrations.
- OAuth 2.0 / SMART-on-FHIR for user-context access.
- Token scope: request narrowest scopes that work. `patient/Observation.read` for one resource type beats `user/*.read`.
- Cache thoughtfully. FHIR responses are PHI; cache layer needs the same protections as the primary store.
- Don't log full FHIR resources at info level. Log resource type + id + outcome.

### "We need to email patients"

- Email is not encrypted in transit by default between mail providers. Patient-facing email containing PHI is a long-discussed gray area.
- Safer: email a notification ("you have a message in the portal"), patient logs in to read it. Most healthcare orgs do this.
- If you must email PHI directly, the patient must have requested email as their preferred channel (right to confidential communications), and you should warn them about email risk. Document the request.
- BAA with the email provider (SendGrid, AWS SES, etc., all offer BAAs).

### "We want to use a third-party error tracker"

- Sentry, Honeybadger, Bugsnag, Rollbar — BAAs available, opt in.
- Default scrubbing rules for PHI patterns. Don't rely on default — configure per your data.
- Server-side errors only by default. Client-side errors include URL fragments, form values, etc., and are higher PHI risk; if you ship them, scrub aggressively.
- Source maps and request bodies — both common leak vectors.

### "Research data"

A complicated area with lots of room for error. The path depends on whether the research is conducted by the covered entity, with what authorization, and under what IRB protocol.

- **Patient authorization** — explicit consent, can be specific to the study.
- **IRB waiver of authorization** — under specific conditions, IRB can waive.
- **Limited Data Set + Data Use Agreement** — for research, public health, healthcare operations.
- **Fully de-identified data** — not PHI, no authorization needed.

For Vanderbilt research environments, the relevant infrastructure is typically VUMC's research data environments (VUMC-managed REDCap, the Synthetic Derivative, BioVU). These have their own access controls and data handling rules; engineering decisions there are made jointly with the research IT team and VUIIS / VICTR governance, not unilaterally.

## State law layering

HIPAA preempts contrary state law unless the state law is more stringent. Several states have enacted stricter rules:

- **California (CMIA)** — broader than HIPAA in some respects.
- **Texas, New York, Washington** — various more-stringent provisions.
- **Tennessee** — generally aligned with HIPAA, with some additions for behavioral health.

Special-protected categories often have stricter rules — substance use disorder records (42 CFR Part 2), mental health, HIV status, genetic information (GINA). If your data includes these, get specific guidance.

## A reasonable architecture for a HIPAA-handling service

```
┌─ Edge ─────────────────────────────────────┐
│ TLS 1.3, HSTS, WAF, rate limiting           │
└──────────┬──────────────────────────────────┘
           │
┌─ Auth ───▼──────────────────────────────────┐
│ SAML/OIDC IdP, MFA, short-lived tokens      │
│ Per-user sessions, automatic logoff         │
└──────────┬──────────────────────────────────┘
           │
┌─ App ────▼──────────────────────────────────┐
│ Authz checks (role + context + minimum-     │
│ necessary), input validation, structured    │
│ logging with PHI redaction                  │
└──────────┬──────────────────────────────────┘
           │
┌─ Data ───▼──────────────────────────────────┐
│ Encrypted at rest (CMK), encrypted in       │
│ transit, immutable audit log of all PHI     │
│ access, daily backups (encrypted), tested   │
│ restore                                      │
└──────────┬──────────────────────────────────┘
           │
┌─ Ops ────▼──────────────────────────────────┐
│ BAA-covered services only, isolated network,│
│ break-glass emergency access, regular access│
│ reviews, vulnerability scanning, IR plan    │
└─────────────────────────────────────────────┘
```

Implementation specifics depend on your stack; the structure is universal.

## Documentation that must exist

The Security Rule requires written policies and procedures. From an engineering standpoint, the artifacts that matter:

- **Risk analysis** — current and reviewed regularly. The 2025 update emphasizes this. It's not paperwork; it's the input to the security plan.
- **Security plan / safeguard documentation.**
- **Incident response plan** — including breach notification.
- **Access management procedures** — provisioning, review, deprovisioning.
- **Audit log review procedures** — frequency, who, what triggers escalation.
- **Backup and disaster recovery plan**, including tested restore.
- **Sanction policy** — what happens to people who violate.
- **Training records** — every workforce member with PHI access trained annually.
- **BAAs** — current, signed, on file, scoped correctly.

These are typically owned by the Privacy/Security Officer, not engineering. But engineering's architecture decisions need to be reflected in them, and the audit trail of "we made this change for this reason" should be preserved.

## Common anti-patterns

- **PHI in URLs.** Patient ID in path, MRN in query string. URLs go in logs, browser history, referrer headers, error trackers. Use opaque IDs in URLs and resolve server-side.
- **PHI in logs because nobody set up redaction.** Default for most logging libraries is to log everything passed in.
- **Shared service accounts** for "the integration" or "the cron job." No way to attribute access. Use per-service identities with OIDC/workload identity.
- **PII/PHI in commit messages, ticket descriptions, or support tickets.** PRs reference real patient cases. Train people; redact.
- **Test environments with real PHI** because "we needed real data to test." Use synthetic data or de-identified extracts.
- **`SELECT *` from PHI tables for reports.** Minimum necessary applies; pick fields.
- **"Free tier" or consumer SaaS used with PHI** because someone signed up with a credit card. No BAA, no PHI.
- **Mobile apps storing PHI offline without device encryption requirements** and without remote wipe.
- **Old data that nobody owns**, in old systems, with old credentials, accessible from old VPNs. Clean up. Decommissioned systems with PHI are a breach waiting to happen.
- **A single "admin" role that can see everything.** Even admins should have minimum-necessary scoping for clinical data, with break-glass for emergencies.
- **Backup tapes / cloud backups not encrypted.** Re-read the safe harbor section.
- **"We'll add HIPAA compliance later."** Bolted-on compliance is incomplete compliance.
- **Generic web analytics (GA, Hotjar) on pages displaying PHI.** Even without PHI in URLs, the session may capture form fields, screen recordings, etc. OCR has been very active here in 2023-2025.
- **Self-attesting that a vendor is "HIPAA compliant" without a signed BAA.** No BAA, no compliance.

## Where this skill ends and others begin

- For **how to actually build audit logging**: see `audit-logging`. HIPAA imposes additional retention and review requirements; the engineering shape is the same.
- For **PII handling generally**: see `pii-handling`. PHI is a subset of PII with extra rules; the general practices apply.
- For **classification of Vanderbilt data and the AI tool matrix**: see `vanderbilt-data-classification`.
- For **secrets and key management**: see `secrets-management`. KMS, rotation, etc.
- For **AuthN/AuthZ patterns** including session timeouts, MFA, RBAC: see `authn-authz`.

For any actual decision affecting compliance posture, **route to your Privacy/Security Officer**. This skill is a starting point for engineering reasoning, not a replacement for institutional governance.
