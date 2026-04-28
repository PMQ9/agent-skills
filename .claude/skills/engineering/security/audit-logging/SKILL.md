---
name: audit-logging
description: Design, implement, and review audit logging for any system handling student data, authentication events, authorization decisions, administrative actions, data access, exports, or third-party disclosures. Use whenever the work involves logging, telemetry, observability, "who did what when," compliance reporting, FERPA disclosure logs, or post-incident forensics. Trigger even when not explicitly asked — phrases like "track usage," "show recent activity," "let admins see who accessed this," "send to Splunk/Datadog," "background job that exports data," or "vendor sync" all need audit logging baked in. Logs are dual-use — they're how you prove compliance *and* how you leak PII if done wrong; this skill covers both sides. Audit logging is required by FERPA § 99.32 for disclosure tracking and is the only way you'll ever reconstruct an incident.
---

# Audit Logging

Two distinct kinds of logs, often confused:

- **Application logs / debug logs** — for engineers debugging behavior. Verbose, ephemeral, may include things you wouldn't want in a permanent record.
- **Audit logs** — for compliance, security forensics, and FERPA's required disclosure log. Structured, append-only, retained, tamper-evident, narrowly scoped.

This skill is mostly about audit logs. The two should be on separate pipes with separate retention and separate access controls. Mixing them is how PII ends up in Datadog forever.

## What an audit log entry must contain

Every audit event captures, at minimum:

| Field | Description |
|---|---|
| `event_id` | UUID, unique per event |
| `event_time` | ISO-8601 timestamp with timezone, server-generated, NTP-synced |
| `event_type` | Enumerated string: `auth.login`, `data.read`, `data.export`, `authz.deny`, `admin.role_change`, etc. |
| `actor_id` | The principal performing the action |
| `actor_type` | `user`, `service`, `system`, `impersonator+target` |
| `actor_ip` | Client IP (with care — see "log hygiene" below) |
| `request_id` | Correlates with the request across services |
| `resource_type` | `student`, `transcript`, `course`, `grade`, etc. |
| `resource_id` | The specific resource touched |
| `action` | `read`, `create`, `update`, `delete`, `export`, `disclose` |
| `outcome` | `success`, `denied`, `error` |
| `reason` | For authz decisions: the rule that fired (`instructor_of_record`, `legitimate_educational_interest`) |
| `metadata` | Optional structured context — *never* the protected payload itself |

For FERPA disclosure logs specifically (§ 99.32), additional fields:

| Field | Description |
|---|---|
| `disclosure_recipient` | Who received the data (party, organization) |
| `disclosure_purpose` | Stated purpose of the disclosure |
| `disclosure_basis` | The exception relied on (e.g., `school_official_legitimate_educational_interest`, `student_consent_id`, `health_safety_emergency`, `subpoena_id`) |
| `records_disclosed` | What records or fields were disclosed |

## What to log

**Authentication events**
- Login success and failure (with the reason for failure category — wrong password vs MFA failed vs locked — but not the password)
- Logout
- Password change, MFA enrollment, MFA reset, recovery flows
- Session creation, renewal, revocation
- SSO assertions received

**Authorization events**
- Every authz decision on protected data, success *and* deny. Denies are the security signal; successes are the FERPA disclosure trail. Don't drop denies because they're "noisy" — they're the most valuable entries when something goes wrong.

**Data access**
- Reads of education records (FERPA disclosure log territory).
- All writes — create, update, delete — to records of any sensitivity.
- Bulk operations: exports, reports, queries returning >N rows. Log the query and the count, not necessarily the rows.

**Administrative actions**
- Role assignments and revocations
- Permission changes
- Configuration changes (especially security-relevant: feature flags, allowlists, retention policies)
- Account creation / suspension / deletion
- Impersonation start and end, with both real and impersonated actor

**Integration / outbound events**
- Every outbound disclosure to a third party (vendor, school, parent, agency)
- API key issuance, rotation, revocation
- Webhook deliveries containing student data
- Files written to S3 / cloud storage / shared drives
- Emails sent that contain student data (the metadata of the send, not the body)

**Security-relevant events**
- Rate limit triggers
- WAF blocks
- CSP violation reports (from `report-uri` / `report-to`)
- Errors at security boundaries (auth middleware crashed, policy engine unavailable)

## What NEVER to log

This is the half people skip. Audit logs become incidents when they contain things they shouldn't.

- **Passwords** — even on failed login. Don't log the attempt's password "for debugging." Don't log the hash.
- **Full tokens, secrets, API keys, MFA codes** — log a fingerprint (e.g., last 4 chars or a hash) if you must correlate.
- **Session IDs** — log a derived ID for correlation, not the actual session ID.
- **Full SSNs / government IDs** — store and log the last 4 only, if at all.
- **The protected payload itself** — log that "transcript for student 12345 was disclosed to advisor 678," not the contents of the transcript.
- **Free-text fields that may contain PII** — advising notes, support ticket bodies, message contents. If you must log them, redact.
- **Authorization headers, cookies, full request bodies** for any sensitive endpoint.
- **PII in URL paths / query strings** — and never log query strings indiscriminately, since other code may put PII there. (Better: design URLs not to contain PII in the first place. See `pii-handling`.)
- **PHI** if it's somehow in scope (HIPAA-protected data has its own rules and shouldn't be in this system).

A good rule: if you wouldn't put it on a billboard, don't put it in a log line. The disclosure log proves *that* a transcript was disclosed; it does not contain the transcript.

## Log hygiene patterns

**Redact at the source.** Build a redaction layer in your logging library so sensitive fields are stripped before they hit any sink. Don't rely on downstream filtering — once it's in Datadog, the "delete" doesn't always actually delete.

```python
# Redaction applied by the logger — recursive so nested PII does not leak.
REDACT_FIELDS = {"password", "ssn", "dob", "transcript", "grade", "authorization", "cookie", "api_key"}

def _scrub(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in REDACT_FIELDS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value

def safe_log(level, event, **kwargs):
    logger.log(level, event, extra=_scrub(kwargs))
```

A top-level-only scrubber leaks anything nested (e.g. `{"user": {"ssn": "..."}}`); the recursive form above matches the scrubber in `pii-handling`.

**Structured, not stringified.** JSON or a structured logging framework. Free-form `f"User {user.email} did {action} on {resource}"` makes redaction impossible and parsing fragile.

**Stable schemas with versioning.** Add a `schema_version` field. When you change the shape of audit events, bump it; downstream consumers (and the registrar's auditor) need to be able to read history.

**Correlation IDs across services.** Every request gets a `request_id` (or trace ID) at the edge, propagated to every downstream service in headers, attached to every log line. Without this, reconstructing an incident is archaeology.

**Server-generated timestamps.** Never trust the client's clock. Use UTC + ISO-8601 with timezone. NTP-sync your hosts.

**Log the fact, not the value.** "User changed email" with a redacted before/after is a security event. "User changed email from a@b.com to c@d.com" is leaking PII into logs. If you need before/after for support, store it in the application database with proper access controls, not in logs.

## Tamper-resistance

Audit logs that the application can rewrite are not audit logs. Threats to plan for:

- Insider with DB access deletes incriminating rows.
- Attacker with code execution rewrites recent entries to cover tracks.
- Bug deletes a day's worth of logs.

Mitigations, in increasing order of strength:

1. **Append-only by convention** — application code never updates or deletes audit rows. DB role granted only `INSERT` on the audit table. Catches accidental, not malicious.
2. **Separate sink** — audit events sent to a logging service (CloudWatch, Splunk, GCP Logging, S3 with object lock) where the *application's* credentials can't delete them. Different IAM principal owns retention.
3. **WORM storage** — S3 Object Lock in compliance mode, write-once-read-many. Required for some regulated environments; useful here.
4. **Hash chaining** — each entry includes a hash of the previous entry. Any deletion or edit breaks the chain and is detectable. Inexpensive, valuable; consider for the FERPA disclosure log specifically.
5. **External anchoring** — periodic Merkle root published to a trust anchor. Overkill for most academic apps, but exists.

Decide the level deliberately. For FERPA disclosure logs, you should be at least at level 2 — the application that does disclosures cannot also delete the record of those disclosures.

## Performance and reliability

Audit logging cannot be a performance bottleneck or it will be turned off "temporarily" and stay off.

- **Async write paths.** Producer puts the event on an in-memory queue or local agent (Vector, Fluent Bit); a separate process ships to the sink.
- **Bounded buffers and backpressure.** Define what happens when the sink is down: drop with a metric? block? spool to disk? The default of "exception bubbling up and breaking the user's request" is wrong.
- **Idempotency.** Retries should not double-log. Use the `event_id` for dedupe at the sink.
- **Don't log inside hot loops** — log once per request with aggregate counts, not once per row.
- **Sample the noisy stuff** (debug logs), but **never sample the audit stream** — every disclosure must be logged exactly once.

## Retention

Different events have different retention. Set this explicitly per event type — don't apply one global retention to everything.

- **FERPA disclosure log entries** — § 99.32 requires the record be maintained as long as the underlying education record is maintained. For most institutions that means decades. Plan storage accordingly; cold storage with long retention is cheap.
- **Authentication / security events** — typically 1–2 years for forensic value.
- **Application debug logs** — 14–90 days, often shorter. These should not contain PII anyway (see above) but assume they do for the purpose of retention.
- **Access logs (HTTP)** — 30–180 days, balanced against the fact that they may contain PII in URLs (avoid that — see `pii-handling`).

Document the retention policy. Make it queryable. Verify with a periodic spot-check that old data is actually being purged from the systems you intended.

## Access controls on the logs themselves

The audit log is itself a sensitive dataset — it lists who looked at what. Treat it like an education record:

- Read access only to security, audit, and compliance roles. Engineering on-call may need read for incident response — log those reads too (yes, recursive — log access to the audit log).
- No raw PII in fields that are visible to broad operations dashboards.
- Export of audit data is itself a disclosure-loggable event.

## Log review

Logs you don't read are stage props. At minimum, set up:

- **Real-time alerts** for high-signal events: repeated authz denies, successful logins from impossible-travel locations, mass exports, role escalations, MFA disablements, audit-log gaps.
- **Periodic review** of disclosure log samples — weekly is fine for a small system. Confirms the disclosure-basis values look right and unexpected categories aren't appearing.
- **Anomaly detection** on access volume per actor, especially for staff roles with broad access.

## Concrete patterns

**Logging a FERPA-relevant disclosure**

```python
def disclose_transcript(actor, student_id, recipient, purpose, basis):
    transcript = transcripts.get_for_actor(actor, student_id)  # already authz-checked
    audit.emit(
        event_type="ferpa.disclosure",
        actor_id=actor.id,
        actor_type="user",
        resource_type="transcript",
        resource_id=student_id,
        action="disclose",
        outcome="success",
        disclosure_recipient=recipient.identifier,
        disclosure_purpose=purpose,
        disclosure_basis=basis,                # e.g. "transfer_school_99_31_a_2"
        records_disclosed=["transcript_official"],
        request_id=current_request_id(),
    )
    deliver(transcript, recipient)
```

**Logging an authz denial**

```python
def require_can(actor, action, resource):
    decision = policy.evaluate(actor, action, resource)
    if not decision.allowed:
        audit.emit(
            event_type="authz.deny",
            actor_id=actor.id,
            resource_type=resource.type,
            resource_id=resource.id,
            action=action,
            outcome="denied",
            reason=decision.rule_id,            # the rule that fired
            request_id=current_request_id(),
        )
        raise HTTPNotFound()
    audit.emit(
        event_type="authz.allow",
        actor_id=actor.id,
        resource_type=resource.type,
        resource_id=resource.id,
        action=action,
        outcome="success",
        reason=decision.rule_id,
        request_id=current_request_id(),
    )
```

**Logging an export**

```python
def export_roster(actor, course_id, fmt):
    rows = roster.for_course(actor, course_id)  # authz scoped
    audit.emit(
        event_type="data.export",
        actor_id=actor.id,
        resource_type="roster",
        resource_id=course_id,
        action="export",
        outcome="success",
        metadata={"format": fmt, "row_count": len(rows), "fields": ROSTER_FIELDS},
        request_id=current_request_id(),
    )
    return render(rows, fmt)
```

Note: `metadata` records the *shape* of the export (count, fields, format) — not the rows themselves.

## Review checklist

- Are sensitive operations (login, authz, data access, exports, admin actions) logged?
- Is each log line structured and free of secrets, tokens, passwords, full PII payloads?
- Is there a `request_id` flowing through services?
- Is the audit sink separate from application debug logs?
- Can the application code that writes the log also delete it? (If yes, fix.)
- Is FERPA disclosure data captured in a form that can be exported for a § 99.32 request?
- Is retention set per event type, with disclosure log retention long enough to match the underlying records?
- Are there alerts on the events that matter?
- If logs go to a third-party SaaS (Datadog, Splunk Cloud), is that vendor approved for FERPA-protected metadata, and is the data sent to them appropriately scoped?
