---
name: pii-handling
description: Handle personally identifiable information (PII) correctly throughout its lifecycle — collection, storage, transit, processing, derivation, sharing, and deletion. Use whenever the work involves student names, IDs, SSNs, dates of birth, addresses, phone numbers, emails, parent/guardian info, demographic data, photos, biometrics, financial data, or any combination of fields that could identify an individual. Trigger on phrases like "user profile," "import this CSV," "send email to students," "store this in S3," "URL with the student ID," "pass this to the LLM," "cache this," "backup," "logs," "anonymize," or "share with the vendor." PII handling sits underneath FERPA — FERPA tells you the *rules*, this skill tells you the *engineering* for safely storing, moving, and deriving from PII without leaking it. Re-identification is a real risk even when names are removed; treat anything resembling PII as PII.
---

# PII Handling

PII = any data that can identify a person, alone or in combination with other data. In a higher-education student system, the surface includes:

- **Direct identifiers**: name, student ID (institutional username/netID, etc.), SSN, government ID, biometrics, photo, voice
- **Quasi-identifiers**: DOB, ZIP, gender, ethnicity, major, cohort year, country of origin — combine 3 of these and you can usually pick out a single student
- **Contact**: address, phone, email (institutional and personal), emergency contacts
- **Family**: parent/guardian names, contact info, financial info, dependent status
- **Educational**: see `ferpa-compliance` — this is where the FERPA scope lives
- **Financial**: aid awards, balances, bank info, payment cards
- **Health**: disability accommodations, immunization records (often FERPA, sometimes HIPAA — escalate if HIPAA-scope)

The legal regime depends on the data: FERPA for education records (most of the above), GLBA for financial data tied to aid, HIPAA for true medical records, state breach-notification laws (the patchwork now spans CO/VA/CT/UT/TX/FL/OR/IA/DE/NJ/IN/MT and others — confirm against the institution's home state and any state where data subjects reside), PCI-DSS 4.0 for payment cards (effective March 2025), and the institution's own data-classification policy. Don't try to memorize the matrix — escalate to the privacy office for novel data flows.

This skill covers the engineering. Pair with `ferpa-compliance` for the legal rules and `application-security` for transport and injection concerns.

## The lifecycle: minimize, protect, expire

Three phases, each with its own discipline.

### 1. Collection — minimize at the source

The PII you don't collect can't leak. Before adding a field to a form, an API, or a data import:

- **Need test.** What feature requires this? If you remove the field, what stops working? If the answer is "nothing right now, but maybe later," remove the field.
- **Granularity test.** Do you need DOB, or just "≥18?" Do you need full address, or just ZIP for a region report? Do you need "Hispanic/Latino" granularity, or just an enrollment count?
- **Source-of-truth test.** Is this already in the SIS / Banner / Workday / IdP? Pull it on demand, don't replicate it. Your copy will drift; the SIS won't.
- **Retention test.** How long will you hold this? Set a TTL at write time. Default to short.

```python
# WRONG — copies SIS into a denormalized "user_profile" with full PII
user_profile = {
  "vunet_id": "abc123",
  "first_name": "...",
  "last_name": "...",
  "ssn": "...",            # why does this app have an SSN?
  "dob": "...",            # is age really needed, or just over-18?
  "address": "...",        # used by what feature?
  "parent_email": "...",   # are you sure you have basis to store this?
}

# RIGHT — store the minimum, fetch the rest from the SIS at request time, with caching policy
user_session = {
  "vunet_id": "abc123",
  "display_name": fetch_from_sis(vunet_id, fields=["display_name"]),  # short TTL cache
  "is_active_student": fetch_from_sis(vunet_id, field="enrollment_status") == "active",
}
```

Fewer fields, shorter retention, fewer attack vectors, faster onboarding through the registrar.

### 2. Storage — encrypt, scope, segregate

**Encryption at rest.** Database-level (TDE) is table stakes. For sensitive fields (SSN, DOB, account numbers, anything that would warrant breach notification), add field-level encryption with keys held in a KMS:

- Application requests an encrypt/decrypt operation from KMS; the keys never leave KMS.
- Different fields get different keys when feasible — limits blast radius of a key compromise.
- Use authenticated encryption (AES-GCM, ChaCha20-Poly1305). Never raw AES-CBC without integrity.
- Rotate keys on a schedule; KMS handles versioning so old data can still be read.
- The DB credentials and the KMS key access should belong to *different* IAM identities so an attacker who gets one cannot decrypt by themselves.

```python
# Field-level encryption pattern
class Student(Base):
    id = Column(String, primary_key=True)
    display_name = Column(String)                       # not separately encrypted
    ssn_ciphertext = Column(LargeBinary)                # encrypted via KMS
    ssn_last_four = Column(String(4))                   # for display / search

    @property
    def ssn(self):
        if not self.ssn_ciphertext:
            return None
        return kms.decrypt(self.ssn_ciphertext).decode()
```

**Tokenization** for PII used as keys. If you need to reference a student in many systems, use an internal opaque ID (UUID) — never the raw SSN, government ID, or even the student ID — as the join key in non-authoritative systems. The mapping lives in one secured store.

**Hashing** for "is this the same person as before" checks where you don't need to recover the value. HMAC with an institution-wide salt held in KMS is appropriate; plain SHA-256 is not (rainbow tables on common values like SSNs are trivial).

**No PII in URLs.** URLs end up in browser history, server access logs, referer headers, CDN logs, email previews, screenshots, error trackers. Use POST bodies or path segments that are opaque IDs, not paths like `/transcripts?ssn=...` or `/student/[email protected]`.

**No PII in client-side storage** (`localStorage`, `IndexedDB`, service worker caches) unless the device is dedicated and known. SPAs love to cache for performance — be deliberate about what's cached and clear it on logout.

**Backups inherit the same protections.** Restoring a backup to a less-secure environment for "testing" is a routine cause of breaches. Backups must be encrypted with separately-managed keys; restore paths must enforce the same access controls and ideally use scrubbed/synthetic data for non-prod.

**Segregate environments.** Production PII should never exist in dev or staging. If a developer needs realistic data, use synthetic data, masked extracts, or differential-privacy-treated samples. The shortcut of "I just copied prod to my laptop" is how careers end.

### 3. Transit — TLS, mTLS, and don't leak via metadata

- **TLS 1.2 minimum, 1.3 preferred**, modern cipher suites only. No SSLv3, no TLS 1.0/1.1, no RC4, no export ciphers.
- **HSTS** with `max-age` ≥ 1 year and `includeSubDomains` once you've confirmed all subdomains are HTTPS.
- **Certificate pinning** for mobile apps making sensitive calls; not typically for browser apps.
- **Internal traffic is not exempt.** Service-to-service calls inside the cluster carry student data and deserve TLS; mTLS adds identity. "It's behind the firewall" is not a security argument.
- **Don't put PII in headers** that get logged by intermediaries. The `Authorization` header is special-cased; arbitrary `X-Student-Email` headers are not.
- **Email is not a secure channel.** Email containing PII to anything other than an institutional, encrypted-at-rest mailbox is a disclosure event. Prefer secure messaging via the application; if email is required, send a notification with a link, not the data.

### 4. Processing and derivation — derived data is still PII

Computing on PII does not magically de-identify it.

- **Aggregations and counts**: small cells re-identify. A report saying "1 student in MajorX, Cohort 2025, from CountryY, on aid tier Z" is a disclosure. Suppress small cells per institutional policy (often n<10, sometimes higher; see `ferpa-compliance`).
- **De-identification has a real legal definition** under FERPA § 99.31(b): all PII removed *and* a reasonable determination that re-identification by someone in the school community is not possible considering reasonably available information. Stripping name and ID does not meet this on its own.
- **Pseudonymization** (replacing IDs with random tokens, keeping a map) still leaves you with PII — the map plus the data is recoverable. Useful for limiting blast radius internally; not equivalent to de-identification.
- **k-anonymity / l-diversity / differential privacy** are real tools when you must publish aggregate or research data. Out of scope for most app code, but be aware these exist when stakeholders ask for "anonymized" data.

### 5. Sharing — every outbound flow is a disclosure

Every place PII leaves your system is a disclosure event with a FERPA basis (or it shouldn't be happening). See `ferpa-compliance` for the legal framing and `audit-logging` for what to record.

Engineering pre-flight for any new outbound flow:

- What recipient? Approved as a school official by procurement / privacy?
- What fields? Minimum necessary?
- What encryption in transit and at rest at the recipient?
- What deletion or revocation path exists?
- Is FERPA-block honored for affected students?
- Is the disclosure logged?

**LLMs and AI features** are a special case. Sending student data to a model provider is a disclosure to that provider. Permissible only if the provider qualifies as a school official under contract with appropriate data-use restrictions, the data is genuinely de-identified per § 99.31(b), or you have explicit consent. Using a "no-training" enterprise tier is not by itself sufficient — the provider still receives the data. Check before piping anything sensitive to an external API. Even prompt context counts.

**Vendor data sync** — CSVs to a vendor, batch jobs, webhook integrations. These need:
- A contract / DPA covering the data
- A documented field-level scope (you sent `name, email`, not the whole roster row)
- An audit-log entry per send
- A rotation/removal path when a student opts out or leaves

### 6. Deletion and amendment — the lifecycle ends

FERPA gives students the right to inspect, and (with some constraints) to request amendment of, their records. Build for this from day one; retrofitting deletion across a denormalized data lake is misery.

- **Right to access (your own records)** — every student-facing system needs an export-self path that produces what's held about that student.
- **Right to amend** — workflows for correction requests; in code, plan for an "amend in place" or "supersede with reason" pattern, not "hard delete and rewrite history" which would destroy the audit trail.
- **Retention and purge** — once records are out of retention, purge. Verify the purge ran. Verify it ran in backups and replicas, not just the primary.
- **Deletion under FERPA**: most education records are retained for years per institutional policy and accreditation requirements. Don't surprise-delete records that the institution must retain. The privacy office sets the policy.
- **Tombstones in audit logs**: the audit log of an action persists even after the underlying record is purged — that's by design. The log entry should reference the deleted record by its opaque ID, not embed the deleted PII.

## Anti-patterns to ban from the codebase

- `print(user)` / `console.log(student)` / `logger.info(record)` that dumps a full object — even in dev. Build a `__repr__` / `toString` that redacts.
- Sending stack traces with request bodies to error trackers (Sentry, Bugsnag, Rollbar) without scrubbing. Configure scrubbing rules at the SDK level for these tools.
- Saving uploads (CSVs, transcripts) to a public-readable bucket "temporarily."
- "We'll just hash the SSN" — without a salt held in a KMS-style secret, this is not protection.
- Caching student records in `localStorage` for "performance."
- Building "search by SSN" or "search by DOB" features — the few legitimate uses can use a tokenized or last-4 search.
- Treating an email address as non-PII because it's "just an email."
- Auto-CC'ing student data to a Slack channel, Teams chat, or shared mailbox for "visibility."
- Pulling prod data into a dev DB to repro a bug. Use a synthetic seed; if you genuinely need prod data, it's a documented, approved, time-bounded process — not a `pg_dump` to your laptop.

## Concrete patterns

**Safe object representation**

```python
class Student:
    def __init__(self, id, ssn, display_name, ...):
        self.id = id
        self._ssn = ssn          # leading underscore signals private
        self.display_name = display_name

    def __repr__(self):
        return f"Student(id={self.id})"  # never include _ssn / dob / etc

    def __str__(self):
        return f"Student {self.id}"

    def to_audit_dict(self):
        return {"id": self.id}   # for audit logs
```

**Error scrubbing for Sentry / Bugsnag**

```python
SENSITIVE_KEYS = {"ssn", "dob", "password", "token", "authorization", "cookie", "transcript", "grade"}

def scrub_event(event, hint):
    def scrub(obj):
        if isinstance(obj, dict):
            return {k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else scrub(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [scrub(x) for x in obj]
        return obj
    return scrub(event)
```

**Field-level encrypt with KMS**

```python
def encrypt_pii(plaintext, key_id="ssn-key"):
    return kms.encrypt(KeyId=key_id, Plaintext=plaintext.encode())["CiphertextBlob"]

def decrypt_pii(ciphertext):
    return kms.decrypt(CiphertextBlob=ciphertext)["Plaintext"].decode()
```

**Opaque IDs in URLs**

```python
# WRONG
GET /api/students/123-45-6789/transcript

# WRONG
GET /api/students/[email protected]/transcript

# RIGHT
GET /api/students/01HXYZ.../transcript        # opaque ULID
# server-side: 01HXYZ -> internal student id, scoped to the actor
```

## Review checklist

- Is every new field justified by a current feature, with a documented retention?
- Is sensitive data encrypted at rest with a key the application alone cannot retrieve?
- Is TLS enforced everywhere, including service-to-service?
- Are URLs free of PII (no emails, IDs that mean something, query params with sensitive values)?
- Are logs and error reports scrubbed at the SDK level?
- Does any new outbound flow have an approved recipient, a DPA, scoped fields, and disclosure logging?
- Is small-cell suppression in place for any aggregate output?
- Is there a delete-self / export-self path?
- Are backups encrypted, segregated, and kept out of non-prod?
- Are dev/test environments using synthetic data, not prod?
- If an LLM is in the path, has the privacy office signed off and is the provider a school-official under contract?

## When to escalate

- Any new system or external party would receive student data.
- Any new field type you haven't classified before (biometrics, geolocation, behavioral telemetry).
- Any aggregate / "anonymized" report that will be published outside the institution.
- Any deletion / purge action that affects a record under retention obligations.
- Any incident or near-miss involving PII exposure.

The privacy office and the registrar own these calls. Engineering implements within the policy they set, and asks early when the path isn't clear.
