# Current Threat Landscape

<!-- update-metadata: keep this block at the top; update mode restamps ONLY this block each run (the entry sections below are an append log, never rewritten or deleted) -->
- **Last updated:** 2026-06-07
- **Updated by:** update news mode (see SKILL.md)
- **Sources consulted:** CISA KEV, NVD, MITRE, OWASP, Unit 42, Mandiant/Google, CrowdStrike, Talos, Rapid7
- **Entries:** 12

This file grounds advice in what is actually being exploited right now. It is an append log:
update mode adds new entries at the top of the relevant section and leaves older ones in place
for history. The discipline that keeps it readable is **one concise line per entry** — date,
title/CVE, a clause on impact, a short lesson, and a whitelisted source link. No multi-line
blocks. Every entry cites a dated source from the allowlist (`assets/trusted_sources.json`).

> **Entry format** (one line; newest first within each section):
> `- **YYYY-MM-DD** — <title> (<CVE/id>): <what + impact in one clause>. → <one-clause lesson>. [source](<whitelisted URL>)`

## Actively exploited vulnerabilities (CISA KEV and vendor reporting)

- **2026-06** — Mirasvit Full Page Cache Warmer (CVE-2026-45247): deserialization of untrusted data, exploited for code execution. → Never deserialize untrusted bytes into live objects. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- **2026-06** — PAN-OS GlobalProtect auth bypass (CVE-2026-0257): forged override cookies create unauthorized VPN sessions on unpatched devices. → Validate auth tokens server-side; patch edge/VPN appliances fast. [Unit 42](https://unit42.paloaltonetworks.com/)
- **2026** — Linux LPE "Copy Fail" (CVE-2026-31431): unprivileged local user gets root on most distros (kernels ~2017+). → Assume footholds escalate; least privilege + segmentation bound blast radius. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- **2026** — Trend Micro Apex One traversal (CVE-2026-34926): `../` directory traversal to unauthorized file access. → Canonicalize and confine all file paths to a base dir. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- **2026** — Langflow origin-validation error (CVE-2025-34291): request forgery against exposed LLM-app-builder instances. → Treat LLM infra as production attack surface. [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)

## AI / coding-assistant security (the fast-moving front)

- **2026** — AI-generated code carries ~2.7x more vulnerabilities, concentrated in injection, XSS, hardcoded secrets (~40% more). → Always run the AI-code pass in `ai-assisted-code-risks.md`. [OWASP GenAI](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- **2025** — Prompt injection in PR descriptions → RCE via coding assistant (CVE-2025-53773, CVSS 9.6): hidden instructions drove attacker-controlled edits. → Model-fed content is an untrusted boundary; never let generated output reach a sink unchecked. [NVD](https://nvd.nist.gov/)
- **2025** — Prompt injection broadly exploitable; OWASP keeps it #1 for LLM apps. → Design assuming injection succeeds; contain blast radius (least privilege, human approval, output validation). [OWASP GenAI](https://genai.owasp.org/llm-top-10/)
- **2026** — Slopsquatting / package hallucination: attackers register the package names LLMs invent; install runs malware. → Verify every AI-suggested dependency exists and is genuine; pin, lock, scan. [OWASP](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

## Notable campaigns and breaches (context for threat models)

- **2026** — China-linked espionage vs Microsoft IIS (cluster "OP-512"). → Internet-facing web servers are prime espionage surface; patch, harden, monitor. [Microsoft](https://www.microsoft.com/security)
- **2026** — World Cup phishing infra "GHOST STADIUM": 300+ cloned FIFA domains harvesting credentials/payments. → Event-driven phishing scales fast; passkeys/MFA + takedown monitoring. [Google/Mandiant](https://cloud.google.com/security)
- **2026** — Large-scale breaches via credential theft and third-party access (e.g. ShinyHunters activity). → Identity is the perimeter: phishing-resistant MFA, least privilege, vendor-access reviews. [CrowdStrike](https://www.crowdstrike.com/global-threat-report/)

## Standing reference points (slow-moving, high trust)

- **OWASP Top 10 (web)** — broken access control remains #1. https://owasp.org/Top10/
- **OWASP Top 10 for LLM Applications (2025)** — prompt injection #1; system-prompt leakage, RAG/embedding security, unbounded consumption, excessive agency; separate agentic-AI Top 10. https://genai.owasp.org/llm-top-10/
- **CISA KEV** — authoritative "patch this now" list. https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- **NVD** — canonical CVE detail and CVSS. https://nvd.nist.gov/
- **MITRE ATT&CK** — adversary tactics/techniques for threat modeling. https://attack.mitre.org/
