# Current Threat Landscape

<!-- update-metadata: keep this block at the top; update mode restamps ONLY this block each run (the entry sections below are an append log, never rewritten or deleted) -->
- **Last updated:** 2026-06-07
- **Updated by:** update news mode (see SKILL.md)
- **Sources consulted:** CISA KEV, NVD, Unit 42, Microsoft, Mandiant/Google, CrowdStrike, Talos
- **Entries:** 21

This file grounds advice in what is actually being exploited right now. It is an append log:
update mode adds new entries at the top of the relevant section and leaves older ones in place
for history. The discipline that keeps it readable is **one concise line per entry** — date,
title/CVE, a clause on impact, a short lesson, and a whitelisted source link. No multi-line
blocks. Every entry cites a dated source from the allowlist (`assets/trusted_sources.json`).

> **Entry format** (one line; newest first within each section):
> `- **YYYY-MM-DD** — <title> (<CVE/id>): <what + impact in one clause>. → <one-clause lesson>. [source](<whitelisted URL>)`

## Actively exploited vulnerabilities (CISA KEV and vendor reporting)

- **2026-06-02** — PAN-OS Captive Portal RCE (CVE-2026-0300): buffer overflow in the User-ID Authentication Portal gives unauthenticated root RCE on PA-/VM-Series firewalls; exploited by state-linked cluster CL-STA-1132. → Never expose mgmt/captive portals to the internet; patch edge appliances on disclosure. [Unit 42](https://unit42.paloaltonetworks.com/captive-portal-zero-day/)
- **2026-06-02** — Linux Kernel improper authentication (CVE-2022-0492): cgroups v1 flaw enabling container escape to host root, added to CISA KEV on active exploitation. → Patch kernels and harden container isolation; old CVEs still get weaponized. [CISA KEV](https://www.cisa.gov/news-events/alerts/2026/06/02/cisa-adds-two-known-exploited-vulnerabilities-catalog)
- **2026-06-02** — Android Framework integer overflow (CVE-2025-48595): memory-corruption flaw added to CISA KEV on evidence of active exploitation. → Keep mobile fleets on current security patch level; mobile is in scope for KEV. [CISA KEV](https://www.cisa.gov/news-events/alerts/2026/06/02/cisa-adds-two-known-exploited-vulnerabilities-catalog)
- **2026-05-20** — Ivanti EPMM improper input validation (CVE-2026-6973): exploited against internet-facing endpoint-management servers; added to CISA KEV. → MDM/EMM consoles are high-value targets; patch fast and restrict exposure. [CISA KEV](https://www.cisa.gov/news-events/alerts/2026/05/20/cisa-adds-seven-known-exploited-vulnerabilities-catalog)
- **2026-04-28** — Windows Shell protection-mechanism failure (CVE-2026-32202): bypass enabling network spoofing, added to CISA KEV (CWE-693). → Apply Patch Tuesday promptly; protection-bypass bugs erode other defenses. [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-32202)
- **2026-06** — Mirasvit Full Page Cache Warmer (CVE-2026-45247): deserialization of untrusted data, exploited for code execution. → Never deserialize untrusted bytes into live objects. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- **2026-06** — PAN-OS GlobalProtect auth bypass (CVE-2026-0257): forged override cookies create unauthorized VPN sessions on unpatched devices. → Validate auth tokens server-side; patch edge/VPN appliances fast. [Unit 42](https://unit42.paloaltonetworks.com/)
- **2026** — Linux LPE "Copy Fail" (CVE-2026-31431): unprivileged local user gets root on most distros (kernels ~2017+). → Assume footholds escalate; least privilege + segmentation bound blast radius. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- **2026** — Trend Micro Apex One traversal (CVE-2026-34926): `../` directory traversal to unauthorized file access. → Canonicalize and confine all file paths to a base dir. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- **2026** — Langflow origin-validation error (CVE-2025-34291): request forgery against exposed LLM-app-builder instances. → Treat LLM infra as production attack surface. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)

## AI / coding-assistant security (the fast-moving front)

- **2026-05-07** — Prompt injection → host RCE in AI agent frameworks (Microsoft Semantic Kernel): a single crafted prompt can launch shell commands on the host running the agent. → Treat agent tool-invocation paths as a sink; sandbox execution and validate tool calls. [Microsoft](https://www.microsoft.com/en-us/security/blog/2026/05/07/prompts-become-shells-rce-vulnerabilities-ai-agent-frameworks/)
- **2026** — AI-generated code carries ~2.7x more vulnerabilities, concentrated in injection, XSS, hardcoded secrets (~40% more). → Always run the AI-code pass in `ai-assisted-code-risks.md`. [OWASP GenAI](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- **2025** — Prompt injection in PR descriptions → RCE via coding assistant (CVE-2025-53773, CVSS 9.6): hidden instructions drove attacker-controlled edits. → Model-fed content is an untrusted boundary; never let generated output reach a sink unchecked. [NVD](https://nvd.nist.gov/)
- **2025** — Prompt injection broadly exploitable; OWASP keeps it #1 for LLM apps. → Design assuming injection succeeds; contain blast radius (least privilege, human approval, output validation). [OWASP GenAI](https://genai.owasp.org/llm-top-10/)
- **2026** — Slopsquatting / package hallucination: attackers register the package names LLMs invent; install runs malware. → Verify every AI-suggested dependency exists and is genuine; pin, lock, scan. [OWASP](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

## Notable campaigns and breaches (context for threat models)

- **2026-05** — Mandiant M-Trends 2026: global median dwell time rose to 14 days (from 11), driven by long-term espionage and DPRK IT-worker operations. → Detection still lags persistence; invest in identity monitoring and insider-threat controls. [Google/Mandiant](https://cloud.google.com/blog/topics/threat-intelligence/m-trends-2026)
- **2026-05** — CrowdStrike 2026 Financial Services report: DPRK-nexus actors stole billions in digital assets; MURKY PANDA ran an operational-relay-box network across 150+ endpoints in 36 countries hitting 340 orgs. → Adversaries industrialize with AI deception and ORB infrastructure; assume relay-laundered traffic. [CrowdStrike](https://www.crowdstrike.com/en-us/press-releases/crowdstrike-2026-financial-services-threat-landscape-report/)
- **2026 Q1** — Cisco Talos IR Trends Q1 2026: phishing reemerged as the top initial-access vector, with public administration the most-targeted vertical. → Email remains the front door; prioritize phishing-resistant MFA and user reporting. [Talos](https://blog.talosintelligence.com/ir-trends-q1-2026/)
- **2026** — China-linked espionage vs Microsoft IIS (cluster "OP-512"). → Internet-facing web servers are prime espionage surface; patch, harden, monitor. [Microsoft](https://www.microsoft.com/security)
- **2026** — World Cup phishing infra "GHOST STADIUM": 300+ cloned FIFA domains harvesting credentials/payments. → Event-driven phishing scales fast; passkeys/MFA + takedown monitoring. [Google/Mandiant](https://cloud.google.com/security)
- **2026** — Large-scale breaches via credential theft and third-party access (e.g. ShinyHunters activity). → Identity is the perimeter: phishing-resistant MFA, least privilege, vendor-access reviews. [CrowdStrike](https://www.crowdstrike.com/global-threat-report/)

## Standing reference points (slow-moving, high trust)

- **OWASP Top 10 (web)** — broken access control remains #1. https://owasp.org/Top10/
- **OWASP Top 10 for LLM Applications (2025)** — prompt injection #1; system-prompt leakage, RAG/embedding security, unbounded consumption, excessive agency; separate agentic-AI Top 10. https://genai.owasp.org/llm-top-10/
- **CISA KEV** — authoritative "patch this now" list. https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- **NVD** — canonical CVE detail and CVSS. https://nvd.nist.gov/
- **MITRE ATT&CK** — adversary tactics/techniques for threat modeling. https://attack.mitre.org/
