---
name: ferpa-compliance
description: Apply FERPA (Family Educational Rights and Privacy Act) rules to any code, data model, query, API, report, or feature that touches student data at any institution receiving federal funding. Use whenever the work involves students, applicants, alumni, enrollment, grades, transcripts, advising, financial aid, disciplinary records, parents/guardians, directory info, or anything pulled from the SIS, registrar, or any system of record about a person who is or was enrolled. Trigger even when the request doesn't say "FERPA" — phrases like "show student emails," "export the roster," "send a list to the vendor," "build a dashboard of grades," "let parents see X," or "join this with admissions data" all need this skill. The registrar will block any system that mishandles this; getting it right is non-optional.
---

# FERPA Compliance

FERPA is the federal law (20 U.S.C. § 1232g; implementing regulations at 34 CFR Part 99) governing student education records at any institution receiving federal funding. Get this wrong and the registrar's office will (rightfully) refuse to onboard the system, regardless of how good the rest of the engineering is.

This skill covers the rules you need to apply *while writing code*. It is not legal advice. When in doubt, escalate to the institution's Office of the University Registrar / privacy office — don't guess. The U.S. Department of Education's Privacy Technical Assistance Center (PTAC, studentprivacy.ed.gov) is also a useful authoritative reference.

## The mental model

Every piece of student data falls into one of these buckets. Your code's behavior depends on which bucket:

1. **Education records** — default-protected. Cannot be disclosed without written consent except under specific exceptions.
2. **Directory information** — disclosable *unless* the student has opted out (a "FERPA block" / "directory hold").
3. **Sole-possession records** — personal notes by a single official, not shared. Out of scope for most systems.
4. **Law enforcement unit records** — separate regime, rare in academic apps.
5. **Employment records** — for students whose only role is employment (not as students), excluded from FERPA. Rare.

If you're not sure which bucket something is in, treat it as an education record. False positives cost nothing; false negatives are violations.

## What is an education record

Anything maintained by the institution that is directly related to an identifiable student. This is intentionally broad. Examples:

- Grades, GPA, transcripts, course enrollments, schedules
- Advising notes, degree audits, academic plans
- Financial aid records, billing, payments
- Disciplinary records (with limited exceptions for outcomes of violent crime/non-forcible sex offense findings)
- Disability services records, accommodations
- Application materials, admissions decisions
- Photos used as identifiers in records (e.g., ID card photo tied to a record)
- Email and chat logs in advising/support tools
- Any join of the above with PII

Format does not matter. Paper, database row, S3 object, log line, Slack message — if it's a record about an identifiable student, it counts.

## Directory information

The institution's published directory information categories are the authoritative list — get the current list from the registrar; do not hardcode assumptions. Typical categories at most institutions include name, address, phone, university email, dates of attendance, enrollment status, major, degrees and awards, participation in officially recognized activities, height/weight of athletes, and most-recent previous institution attended.

**The opt-out is the trap.** Any student can request a "FERPA block" / "directory hold" / "non-disclosure flag." Once flagged, *none* of their directory information may be released — not even confirmation that they are or were a student. Your code must:

- Read the FERPA-block flag from the system of record on every request, not from a cache that could be stale by more than a short TTL.
- Filter blocked students out of any output that includes directory info.
- Never expose "this student exists but is hidden" as distinguishable from "this student does not exist." The response to a query about a blocked student should look identical to a query about a non-existent one.
- Treat directory info of a blocked student as an education record — same protection as grades.

```python
# WRONG — leaks existence of blocked students
def get_student_email(student_id):
    student = db.students.get(student_id)
    if student.ferpa_block:
        raise NotFound("Student has FERPA block")  # leaks existence
    return student.email

# RIGHT
def get_student_email(student_id):
    student = db.students.get(student_id)
    if not student or student.ferpa_block:
        raise NotFound()  # indistinguishable response
    return student.email
```

## Consent and the exceptions to consent

Disclosure of an education record requires the student's signed, dated, written consent specifying records, purpose, and recipient — *unless* one of the FERPA exceptions applies. The exceptions you'll see most often in code:

- **School officials with legitimate educational interest.** This is the workhorse exception for internal apps. A "school official" is a person (employee, contractor, vendor) performing a function the institution would otherwise do itself, under direct institutional control of record use. "Legitimate educational interest" means the official needs the record to perform their job. Your access control must enforce both — role *and* need-to-know.
- **Other institutions where the student seeks to enroll** (transcripts to receiving school).
- **Specified officials for audit/evaluation** of federal/state programs.
- **Financial aid** for which the student has applied or which they have received.
- **Accrediting organizations.**
- **Judicial order or lawfully issued subpoena** (with notification requirements).
- **Health or safety emergency.** Narrow. Real, articulable threat.
- **Studies for, or on behalf of, the institution** (research with a written agreement).
- **Parents of a student who is a "dependent" for IRS purposes**, or in the case of a health/safety emergency, or (for students under 21) regarding violations of law/policy concerning alcohol or controlled substances. Note: at the postsecondary level, FERPA rights transfer to the student at enrollment regardless of age. Parental access is the exception, not the default. Don't build "parent portal" features that auto-share grades — require either dependent verification documented by the registrar, or explicit FERPA-compliant student consent on file.
- **Directory information** (subject to opt-out, above).

If the request doesn't fit cleanly into one of these, it needs consent. "We're just emailing it to the vendor we use" is not an exception — vendors can be school officials *only if* the contractual and operational requirements are met, which is a procurement/registrar question, not a developer judgment call.

## What this means for the code you write

**1. Access control is FERPA enforcement.** Every read of an education record must be checked against an authorization rule that maps to a FERPA basis. See `authn-authz`. Roles like "advisor," "instructor of record," "financial aid counselor" must be tied to scoped data — an instructor sees their own course's grades, not the whole university's.

**2. Disclosure logging is required, not optional.** FERPA § 99.32 requires the institution to record each request for, and each disclosure of, personally identifiable information from an education record — *with exceptions* (school officials with legitimate educational interest, directory info, requests with written consent, parties seeking directory info, parties with the student's signed consent for that disclosure, requests by the student themselves). The conservative default for code: log every access and every disclosure with actor, recipient, records disclosed, purpose, legitimate-interest basis, and timestamp. See `audit-logging`. Retention: maintained as long as the underlying record is maintained.

**3. Outbound integrations are the high-risk surface.** Any time data leaves the boundary — email, webhook, S3 export, vendor API, downloaded CSV, BI tool, screen share, support ticket — that is a potential disclosure. Code paths that send data outward must:

- Identify which fields are education records vs directory info.
- Check the FERPA-block flag for each subject.
- Verify the recipient is authorized under one of the exceptions or has consent.
- Write a disclosure log entry.
- Use the minimum data needed (data minimization — see `pii-handling`).

**4. Joins create records.** Joining tables can transform non-record data into an identifiable education record. A list of "people who logged into the LMS" joined to a roster is now an education record. Treat the *result* under the rules, not the inputs.

**5. AI features are disclosures.** Sending student data to an LLM provider is a disclosure to that provider. It is permissible only if the provider qualifies as a school official (under contract, under institutional control, with use restrictions), the data is de-identified per § 99.31(b), or you have consent. Don't pipe transcripts or advising notes to a third-party model without explicit sign-off from the registrar/privacy office and an appropriate DPA. If unsure, *ask* before shipping.

**6. De-identification has a real definition.** § 99.31(b) requires removing all PII *and* applying a reasonable determination that a reasonable person in the school community would not be able to identify the student, including with reasonable available information. Stripping name and ID is not enough — small cell sizes, rare attributes (e.g., the only student in a major+cohort+demographic combo), and joins with public data routinely re-identify. For aggregate reports: suppress small cells (a common threshold is n<10 but the registrar sets the policy), avoid rare-attribute combinations, don't release row-level data even with names removed.

**7. Annual notification and student rights.** FERPA gives students rights to inspect and review their records, request amendment, and consent to disclosures (with exceptions). If you're building anything that holds records, the system needs to support: producing a student's own records on request (right to inspect), correction workflows (right to amend), and the disclosure log (right to know who has accessed their record under § 99.32). Plan these in from the start; retrofitting is painful.

## Concrete checks before merging code

Run through this list mentally on any PR that touches student data:

- Does this code path read or write an education record? (Yes is the default.)
- Whose records? Is a subject-identifier scoping check in place?
- Is the actor authorized under a FERPA basis? Is that basis recorded in the access decision?
- Is the FERPA-block flag honored?
- Are directory-info fields treated separately from education-record fields?
- Are outbound disclosures logged per § 99.32?
- Is data minimized to the fields actually needed? Are sensitive fields encrypted in transit and at rest? (See `pii-handling`.)
- Does this introduce a new third-party recipient? If yes, stop and check the contract / DPA / registrar approval before merging.
- Does this generate aggregates? Are small cells suppressed?
- Does this introduce parent access? If yes, stop and confirm the consent/dependent path.
- If an LLM or external API is in the data path, is it an approved school-official vendor under contract?

## When to escalate

You are not the registrar. Some calls are policy decisions, not engineering decisions. Escalate when:

- A new vendor or LLM provider would receive student data.
- A new disclosure path opens (email automation, webhook, public URL, BI export).
- A new aggregation could re-identify based on small populations.
- A request for data comes in framed as "the [official] needs this for [purpose]" and the legitimate-educational-interest mapping isn't obvious.
- Anyone, ever, asks you to bypass the FERPA-block flag, even for "just one report."
- A subpoena or legal request lands.

The registrar would rather answer a question than clean up a violation. So would you.

## Institution-specific items to pin down (fill in with the registrar)

These are institution-specific and your code should read them from configuration / a policy document, not hardcode. Confirm with the institution's Office of the University Registrar:

- The current published list of directory information categories.
- The exact FERPA-block flag in the SIS and how to read it.
- The list of approved school-official vendors and their data scopes.
- Small-cell suppression thresholds for institutional reporting.
- Disclosure log retention and storage location requirements.
- The authoritative source-of-truth for student status (active, withdrawn, alumnus, deceased) — these change FERPA applicability over time (FERPA continues to apply to records of former students; it ends at death under federal law, though institutional policy may extend protections).

When the registrar gives you these answers, write them into a `FERPA_POLICY.md` in the repo and load them as configuration. Don't bury them in code comments where they'll drift.
