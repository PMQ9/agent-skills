# Reviewing AI-Integrated Changes

Distilled from `ai-solution-architect`, reframed for **reviewing a diff** that
adds or changes AI/LLM functionality. Use this reference only when the change
touches a model call, a prompt, a retrieval/RAG layer, an agent loop, or any
component whose output comes from an LLM.

The architecture lens still applies: an LLM is *one component* with inputs,
outputs, and failure modes — the review asks whether the code keeps it in its
place. This is design-level review, not model tuning and not micro-optimization.

## Is AI even the right tool here? (a legitimate finding)

A diff that reaches for an LLM where deterministic code would serve better is an
architecture finding — it taxes quality, latency, cost, and auditability for no
reason. Flag it (usually Major) when the diff uses a model for work that is:

- a small, well-defined output space with rules you could write down (routing on
  a fixed set, validating an email, sorting, dedup);
- something existing software already does well (search, exact lookup);
- a decision needing determinism/auditability/reproducibility (pricing,
  compliance, regulated decisions) with the model as the *final* say rather than
  an assist;
- high-stakes, where a confident wrong answer costs far more than doing nothing,
  with no human as final authority.

Recommend the deterministic alternative (a query, a small classifier, a rules
layer) for the parts that don't need generation, with the model handling only the
genuinely fuzzy remainder. Don't be dogmatic — if the input is messy/natural and
the output is generative or judgmental, the LLM is likely right; say so.

## Integration pattern — is it named and appropriate?

Most AI features are one of a few shapes. A review should be able to name the one
the diff implements and check it's the simplest that fits:

- **Thin wrapper** (call model → render/store) — the right default for v1.
- **RAG** (fetch context → pass with query) — most of the risk lives in the
  retrieval layer, not the model call.
- **Structured extraction/classification** (free text → schema) — needs tight
  schema + validation + retry.
- **Agent loop** (model chooses tools in a loop) — justified only for genuinely
  unbounded multi-step tasks; otherwise a fixed pipeline is safer.
- **Hybrid pipeline** (rules → classical ML → LLM → human) — usually right at
  scale.
- **Background batch** (offline, cached) — right when input isn't request-time.

Finding shape: a diff that builds an **agent loop** where a fixed pipeline would
do, or a **chatbot** surface where a one-shot extraction / inline suggestion /
cached answer would be cheaper and easier to evaluate. Over-built AI surface is
the same class of finding as over-engineering elsewhere.

## Failure modes the code must handle

For each that applies to the diff, check the code names a response (even
"accepted risk" is valid if stated). A silent gap is the finding:

- **Hallucination** — is a high-stakes generated output grounded in retrieval,
  validated, or gated through human review? Ungrounded free generation feeding a
  consequential path is a finding.
- **Prompt injection** — does the diff feed untrusted content (web pages, emails,
  user uploads, third-party API responses, retrieved docs) into the prompt? If
  so, and especially if the model can then call tools or emit links/actions, this
  is a Critical-class finding. Hand off specifics to `prompt-injection-defense`.
- **Schema violation** — for structured output: is there provider-native
  structured output or validation, one retry with the error fed back, and a
  graceful fallback? Parsing model text with no validation is a finding.
- **Provider outage / rate limit** — is there a fallback (alternate provider or
  smaller model), backoff, and graceful degradation? A hard dependency on one
  endpoint with no fallback on a user path is a finding.
- **Drift** — are model/prompt versions pinned, with a golden eval on change? An
  unpinned model on a critical path is a finding.
- **Cost runaway** — per-request token caps, per-user rate limits, spend circuit
  breakers. An unbounded loop or unbounded fan-out of model calls is a finding
  (design-level, not micro-optimization).
- **Latency tail** — P99 with timeouts and fallbacks; streaming for user-facing
  chat (but streaming doesn't help a downstream consumer that needs the whole
  result).
- **Quiet quality decay** — is there any signal (eval, feedback, spot-check) that
  would reveal outputs getting worse? "We'll see if users like it" is not a
  signal.
- **Cross-tenant / cross-corpus leakage** — when one AI feature serves multiple
  customers/departments, can content from A reach B's output? Check ACL-preserving
  retrieval, per-tenant scoping, and prompt construction. This is a
  contractual/reputational incident, not just a bug — Critical.

## Evaluation is an architectural concern

If the diff ships AI behavior with no way to tell whether it's correct, that's a
design gap worth raising. Look for: a golden set runnable on every change, a
grading approach proportional to stakes (auto-check / model-as-judge / human),
and a regression plan when prompts or model versions change. If the change can't
answer "how would we know if this got worse?", say the feature isn't finished.
Hand off eval-set design to `test-planning`.

## Human-in-the-loop placement

Check *where* (if anywhere) a human reviews output, and that it matches the
stakes — not "humans everywhere out of caution":

- Pre-output review (approve before user sees) — highest safety, worst latency;
  high-stakes only.
- Post-output sampling — catches drift without slowing the system.
- Escalation on low confidence — needs calibration.
- User-facing feedback (thumbs/corrections) — cheap, biased, useful long-run.
- No human — fine when failure cost is low and volume high; the finding is when
  that's true in reverse (high stakes, no human). Hand off to
  `human-in-the-loop-workflows`.

## Privacy, security, data perimeter

Design-level findings a diff can introduce:

- **Data crossing to the provider** — what data leaves your infrastructure, under
  what agreement/retention? A diff sending PII/regulated data to a model provider
  without that being an established, allowed path is a finding.
- **Prompt/completion logs** — treated like production customer data, or dumped
  to plain logs? Logging full prompts with PII is a finding.
- **Permission scoping** — whose permissions does the AI act under? Handing a
  feature a broad/admin token "because it's easier" instead of per-user scoping
  is a finding.
- **Output exfiltration vectors** — auto-rendered markdown links, HTML,
  pipe-to-tool on model output. Unsanitized model output flowing into a rendered
  surface or a tool call is a finding (overlaps prompt-injection defense).

## Model selection sanity

Not a tuning review, but two design-level notes are fair game:

- **Floor, not ceiling.** Production lives near the model's *worst-case* behavior
  on the task, not the demo. A diff that assumes best-case reliability from a
  model on a critical path, with no validation or fallback, is a finding.
- **Reversibility.** Is the provider call abstracted so switching is a config
  change, not a rewrite? A frontier model hard-wired throughout the codebase is a
  reversibility finding.

## Calibration

- Only raise AI findings for diffs that actually touch AI functionality.
- "Accepted risk," stated explicitly, is a valid answer — the finding is the
  *silent* gap, not the acknowledged trade-off.
- Keep it at the design level: prompt-injection surface, missing eval, unscoped
  tenancy, no fallback, unbounded cost. Do **not** drift into token-level prompt
  micro-optimizations or model latency tuning — those aren't this review.
