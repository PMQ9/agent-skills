# Threat Modeling (macro phase)

Threat modeling answers one question before any code is read: *what could go wrong here, and
who would make it go wrong?* It is the cheapest security activity per bug prevented, because
a design flaw caught on a whiteboard costs a sentence and the same flaw caught in production
costs an incident.

## The four framing questions

Run these in order. They are deliberately simple so they actually get used.

1. **What are we building?** Sketch the system as data flowing between components. You need
   a mental (or literal) diagram: external actors, processes, data stores, and the data flows
   between them. You can't reason about attacks on a system you can't draw.
2. **What can go wrong?** Enumerate threats at each element and flow. STRIDE (below) is the
   workhorse mnemonic for this.
3. **What are we going to do about it?** For each credible threat, pick a response: mitigate
   (add a control), eliminate (remove the feature/flow), transfer (push to a provider), or
   accept (document the risk and move on). Not every threat needs a control — but every
   threat needs a *decision*.
4. **Did we do a good job?** Validate that the controls actually cover the threats, and that
   you didn't introduce new ones. Threat models are living documents; revisit on design change.

## Trust boundaries: where attacks live

A trust boundary is any line data crosses from lower trust to higher trust. Attacks
concentrate here because that's where assumptions get violated. Common boundaries:

- The network edge (internet → your service).
- Between services or tenants (service A → service B; tenant X's data → tenant Y's request).
- Process → OS (user input → shell, file path, SQL, deserializer).
- Untrusted content → an LLM's context window (this is now a first-class boundary — see
  `ai-assisted-code-risks.md` and treat any model-influencing content as untrusted input).
- Client → server. Never trust the client: validation, authorization, and pricing all belong
  on the server. Client-side checks are UX, not security.

For each boundary, ask: what is the most-trusted thing reachable from the least-trusted side,
and what stops the jump?

## STRIDE: a checklist for "what can go wrong"

Apply each category to each element/flow. Most real bugs fall into one of these.

| Threat | Violates | Ask | Typical control |
|--------|----------|-----|-----------------|
| **S**poofing | Authentication | Can someone pretend to be another user/service? | Strong auth, mutual TLS, signed tokens |
| **T**ampering | Integrity | Can data be modified in transit or at rest? | Signing, integrity checks, write authz |
| **R**epudiation | Non-repudiation | Can someone deny an action with no trace? | Tamper-evident audit logs |
| **I**nformation disclosure | Confidentiality | Can data leak to someone unauthorized? | Encryption, authz, minimization |
| **D**enial of service | Availability | Can the system be exhausted or crashed? | Rate limits, quotas, timeouts, backpressure |
| **E**levation of privilege | Authorization | Can someone do more than they're allowed? | Least privilege, authz checks at every step |

## Abuse cases and attack trees

Where a user story says "as a user I can reset my password," the **abuse case** says "as an
attacker I reset *someone else's* password." For each important feature, write the inverted
story. It surfaces missing authorization and rate-limiting almost for free.

An **attack tree** decomposes a goal into ways to achieve it. Root = attacker's objective
(e.g., "read another tenant's invoices"). Children = methods (IDOR on the invoice endpoint,
stolen session, SQL injection, leaked backup). Leaves you can't credibly defend against tell
you where to spend effort. You don't need formal trees for everything — but for the crown-jewel
assets, thinking in goals-and-methods beats thinking in features.

## Ranking what you find

Use rough likelihood × impact. A trivially exploitable bug on an internet-facing,
unauthenticated endpoint that touches money or PII is where you start. A theoretical issue
requiring physical access and a coincidence is where you stop. Resist treating every item as
equally urgent — a flat list of 40 "issues" is as useless as no list, because the reader
can't tell what will actually get them breached.

## When to do this versus jump to code

Do a real threat model when: designing something new, adding a trust boundary (new
integration, new input source, new tenant model), handling money / PII / auth / secrets, or
when the user asks "is this design safe." Skip straight to code review for a small, localized
change inside an already-understood system — but still spend one sentence asking "what's the
worst input that reaches this code, and from where?"
