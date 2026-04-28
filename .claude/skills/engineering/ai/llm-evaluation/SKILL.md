---
name: llm-evaluation
description: Build evaluation systems for LLM applications — choosing what to measure, building golden datasets, designing rubrics and assertions, using LLM-as-judge correctly, calibrating against human ratings, handling variance and statistical significance, running offline and online evals, and building the eval discipline that makes shipping LLM features tractable. Use this skill whenever the task involves measuring LLM quality, regression-testing prompts, comparing models, validating a RAG or agent system, debugging "the prompt seems worse but I can't tell," designing an A/B test for an LLM feature, or any work where someone needs to answer "is the new version better?" with more rigor than vibes. Trigger on terms like "eval," "evaluation," "benchmark," "regression test," "LLM-as-judge," "golden set," "test cases," and similar.
---

# LLM Evaluation

LLM development without evals is debugging in the dark. You change a prompt, the output looks different, and you have no principled way to say whether different is better. Eval discipline is what separates LLM features that improve over time from ones that drift, regress, and lose user trust.

The honest version of this skill: most teams know they should have evals and don't. The barrier is not knowledge but starting cost — the first eval suite feels like a lot of work for one team. This skill covers the fastest path to a useful eval system and the patterns that scale once you have one.

## What evals are for

Evals serve several purposes that share infrastructure but have different design implications:

- **Regression detection.** Catch quality drops when you change a prompt, model, or pipeline component.
- **Improvement measurement.** Quantify whether a change is better, by how much, and on which subsets.
- **Capability mapping.** Find where your system fails — which query types, which input shapes, which user segments.
- **Selection.** Choose between models, prompts, or pipeline configurations.
- **Monitoring.** Track quality drift in production over time.

The same eval set can serve multiple purposes, but the design varies. Regression detection wants stable, representative cases. Capability mapping wants edge cases and known-hard inputs. Monitoring wants production-like distributions, refreshed regularly. Resist the temptation to make one eval set do everything; instead, layer them.

## The minimum useful eval

Before building anything sophisticated, get this:

1. **A list of 20-50 representative test cases**, written by hand based on real or expected user inputs.
2. **A way to run them** — a script that takes a prompt/system/model and produces an output for each.
3. **A way to grade them** — automated where possible, manual review where not.
4. **A scoreboard** — pass rate, broken out by category if cases are categorized.

This much, in a Jupyter notebook or a CLI script, is more than most teams have and enough to catch the obvious regressions. Build it before you build anything else. Anything more sophisticated should be motivated by a concrete need this minimum doesn't meet.

## Building the golden set

The golden set is a list of representative inputs paired with expected outputs (or expected output properties). It is the most valuable artifact in your eval system; treat it as such.

Sources for cases:

- **Real user data.** Sample production traffic, anonymize, hand-label. Highest signal, hardest to bootstrap.
- **Hand-authored.** Domain experts write cases representing the inputs you expect. Fast to start; risks bias toward what authors *imagine* users do, which is not what they do.
- **Synthetic.** LLM-generated cases derived from your docs/data. Useful for filling out coverage; supplement real cases, don't replace them.
- **Adversarial.** Cases targeting known failure modes, edge cases, ambiguity. Critical for catching tail behavior.
- **From bug reports and incidents.** Every quality complaint becomes an eval case. This is non-negotiable: a bug without a test case is a bug that will recur.

A useful target distribution: 60% representative cases (the bread and butter), 20% edge cases (long inputs, unusual formats, multilingual), 20% known-hard or adversarial.

Tag every case with categories — query type, language, length bucket, expected difficulty, source. Aggregate metrics on the whole set hide regressions on subsets. A change that improves overall pass rate by 2% while dropping pass rate on multilingual cases by 15% is a regression you need to see.

## Assertions and rubrics

For each case, define what makes the output good. The strictness depends on the task.

**Exact match.** The output must equal a specific string or structured value. Useful for classification, structured extraction, and any case with a unique correct answer.

**Property assertions.** The output must satisfy one or more checkable properties: contains certain keywords, doesn't contain forbidden phrases, parses as valid JSON, has the right schema, length is in range. Cheap to check; catches a lot.

**Reference comparison.** The output must be semantically equivalent to a reference answer. Hard to automate well; this is where LLM-as-judge enters.

**Rubric grading.** A rubric of 3-7 dimensions (correctness, completeness, format, tone, etc.), each scored 0-N. More expressive than pass/fail; useful when "better" is multi-dimensional.

**Pairwise comparison.** Given two outputs (e.g., from old and new prompt), pick the better one or call them equivalent. Often more reliable than absolute scoring; humans and LLMs both judge "A vs B" better than "rate A out of 10."

A practical pattern: combine cheap automated assertions (parse, schema, keyword) with one expensive judgment per case (LLM-as-judge or human). The cheap assertions catch obvious failures fast; the expensive judgment catches subtle quality issues.

## LLM-as-judge

Using an LLM to grade other LLM outputs is now standard practice. It is also routinely misused. The rules:

**Calibrate against humans.** Hand-grade 50-100 cases yourself. Compare the LLM judge's verdict to yours. Compute agreement (Cohen's kappa or simple accuracy). If agreement is below 0.7, the judge is unreliable — fix it before trusting its scores.

**Use a strong judge.** A small model judging a small model's output produces noise. Use the strongest available model as the judge, even if you'd never use it in production. Judging is one-shot; you can afford the cost.

**Constrain the judge.** Give it a rubric, an output format (structured JSON with reasoning + verdict), and explicit criteria. "Rate this output 1-10" is too open. "Score correctness (0/1), completeness (0/1), tone (0/1), then return JSON" is gradeable.

**Prefer pairwise to absolute.** "Which is better, A or B?" produces lower-variance judgments than "score this from 1 to 10." When you have two versions to compare, use pairwise.

**Mind the biases.** LLM judges are biased: toward longer outputs, toward outputs that look like their own style, toward outputs presented first in pairwise comparisons. Mitigate by rotating order, controlling for length where possible, and validating periodically against humans.

**The judge has its own quality, evaluate it.** When you change your judge prompt, you've changed your eval. Track judge calibration over time and on changes.

A useful pattern: combine LLM-as-judge with a small human-graded set. The human set catches drift in the judge ("did our judge rubric stop working?"); the judge scales out to thousands of cases the humans can't grade.

## Human evaluation

For some questions, only humans can answer. Long-form quality, creative output, anything subjective, anything where the rubric is itself fuzzy.

Practical patterns:

- **Internal review.** Team members grade outputs. Cheap, fast, biased — they know what you want.
- **Expert review.** Domain experts grade. Higher quality, slower, more expensive.
- **External raters.** Crowdsource workers. Scales out but variable quality; needs careful instructions and quality controls (gold-standard items mixed in to detect bad raters).
- **End users.** Implicit signal in production (thumbs up/down, follow-ups, time-to-task-completion). Highest external validity, lowest signal density.

Always grade with a rubric, not raw "is this good." Even informally — write down two or three criteria before you start grading. Rubric-graded humans agree with each other more than open-graded humans.

For high-stakes domains (medical, legal, financial), you may need expert raters and inter-rater agreement metrics. Budget for it.

## Variance and statistical significance

LLMs are non-deterministic. "Pass rate went from 82% to 84%" might be real or might be sampling noise. Treat eval scores like experimental data.

- **Run each case multiple times** (typically 3-5) to estimate variance per case. Cases with high variance ("flaky cases") are either inherently borderline or have an under-specified rubric. Both deserve attention.
- **Compute confidence intervals**, not point estimates. With 50 cases and 80% pass rate, the 95% CI is roughly ±11pp. A change from 80% to 84% on 50 cases is well within noise.
- **Use paired comparisons.** When comparing version A and B, run both on the same cases and compare per-case outcomes. This controls for case difficulty and is much more powerful than comparing pass rates of independent samples.
- **Pre-register the comparison.** Before running, decide what difference would be "meaningful" and what statistical test you'll use. Prevents p-hacking.

For most teams, the right answer is: run more cases and use a paired test. McNemar's test for binary outcomes; paired t-test or Wilcoxon for scalar scores. Software engineers often have an allergy to statistical tests; resist this. Without one, you'll ship regressions and chase noise.

## Eval-driven development

The ideal workflow:

1. Before changing the prompt, run the current version against the eval set. Save baseline.
2. Change the prompt.
3. Run the new version against the eval set.
4. Compare per-case outcomes. Look at every case that changed verdict, especially regressions.
5. Decide whether to ship based on (a) net improvement, (b) absence of meaningful regressions on important subsets, and (c) per-case inspection of changed outputs.

This is closer to how software teams use unit tests than how ML teams use academic benchmarks. The goal is regression-resistance and confidence in changes, not topping a leaderboard.

A common failure: developers run evals on the easy/medium subset because the hard subset is "noise." The hard subset is where regressions hide. Run the whole set; segment the report.

## Online evals

Offline evals run on curated cases. Online evals run on production traffic. They answer different questions:

Offline: "Did this change break anything I know to test?"

Online: "Is the system getting better or worse for real users?"

Online metrics:

- **Implicit signals.** Thumbs up/down, regenerate clicks, copy clicks, conversation length, abandonment rate, time-to-task-completion.
- **Explicit signals.** Surveys, ratings, structured feedback. Lower volume, higher quality.
- **Outcome metrics.** Did the user take the action the LLM suggested? Did the support ticket close? Did the agent complete the task without escalation?

Sample production outputs for periodic offline grading. A small fraction of traffic, judged by LLM-as-judge or humans, gives you a continuous quality estimate that catches drift.

A/B testing LLM features is harder than A/B testing UI changes. Quality differences are subtle; required sample sizes are large; effects can be subgroup-specific (better for power users, worse for new users). Plan the experiment as carefully as you'd plan a search ranking experiment.

## Evaluating different system types

The general patterns above apply, with some specialization.

**RAG systems.** Evaluate retrieval and generation separately, then end-to-end. See `rag-architecture` for retrieval-specific metrics. Faithfulness (answer supported by context) is the central RAG quality metric and needs explicit measurement.

**Agents.** Evaluate end-to-end (did the agent complete the task?) and trajectory-level (right tool? right plan? recovered from errors?). Run multiple times per case — agents have higher variance than single calls. Real environments beat mocks; the failure modes are different. See `agent-design`.

**Chatbots / multi-turn.** Single-turn evals miss multi-turn failures (forgetting context, repeating itself, getting lost). Build multi-turn cases with scripted user follow-ups. The eval "user" can be an LLM playing a character.

**Classification and structured extraction.** Use traditional ML metrics (accuracy, precision, recall, F1) — these tasks have known-correct answers. Per-class breakdowns matter; average accuracy hides class imbalance.

**Open-ended generation.** Hardest to evaluate. Lean on rubrics, LLM-as-judge with strong calibration, and pairwise comparison. Don't pretend you have a single number.

## Cost and infrastructure

Evals are not free. A 500-case eval at 5 runs each, with LLM-as-judge using a strong model, can cost real money per run. Budget accordingly:

- **Eval CI.** Run the full suite on every prompt change in CI. Cost amortizes; regressions caught here are cheaper than regressions caught in production.
- **Cached results.** When the prompt and the case haven't changed, the result is the same. Cache aggressively.
- **Tiered runs.** Smoke set (10 cases, runs in 30s) on every commit; full set (500 cases, runs in 10 minutes) on PRs; extended set (5000 cases, runs in an hour) nightly.
- **Async grading.** Generation runs are fast; LLM-as-judge calls run in parallel afterward. Don't serialize them.

Infra to invest in:

- A way to version eval datasets so you can re-grade old runs against new rubrics.
- A trace store so you can inspect what the model did, not just the verdict.
- A diff view: "show me cases that changed verdict between version A and B."
- A drift dashboard: pass rate over time, per-subset.

You don't need a full vendor product to start. A SQLite database, some Python scripts, and a Streamlit dashboard can carry you a long way. Move to a vendor (Braintrust, Langfuse, Patronus, Weights & Biases, etc.) when the data scale or the team scale demands it.

## Common pitfalls

**Eval rot.** The eval set was built two years ago for a product that no longer exists. Quality on the eval is high; users are unhappy. Refresh continuously from production and from incident reports.

**Train-test contamination.** Eval cases are reused as few-shot examples in the prompt. Pass rate is meaningless. Keep them separate.

**The unrepresentative golden set.** Cases were written by the team during prototyping and reflect what *they* tested, not what users do. Pass rate is high; production complaints come from cases not in the set. Sample from production to fix.

**The single-number obsession.** "We hit 87% on the eval." 87% over what cases, with what rubric, against what baseline, with what variance, broken out how? Reduce evals to actions, not trophies.

**Drift in the judge.** LLM-as-judge model auto-upgraded; rubric agreement with humans drifted; everyone assumes scores are comparable. Pin the judge model and revalidate when you change it.

**No regression budget.** A new feature ships that improves average quality by 5% but tanks pass rate on a critical subset by 30%. Without subset-level reporting, this slips through. Always report subsets.

**Vibes-based shipping.** "I tried it on 5 prompts and it seemed better." This will not survive contact with reality. Run the eval.

**Eval-as-theater.** Team has an eval suite that hasn't been updated in months and isn't gating anything. The metric is a vanity number, not a decision input. Wire evals into the change workflow or delete them.

## A reference workflow

For a small team starting from zero:

1. **Week one.** Hand-write 30 representative cases. Build a script that runs them and saves outputs. Manually grade once.
2. **Week two.** Categorize cases. Add automated property assertions where possible (schema, keywords). Build a simple report (pass rate, broken out by category).
3. **Month one.** Add LLM-as-judge for the cases that need it. Calibrate against your manual grades. Wire the eval into PR checks.
4. **Month two.** Sample production traffic, anonymize, add to the eval set. Add cases for every shipped bug.
5. **Month three.** Add multi-run variance. Build a diff view for comparing eval results across versions.
6. **Ongoing.** Every quality complaint adds a case. Every prompt change runs the eval. Every model change reruns calibration on the judge.

This is unglamorous, slow, and pays back enormously. The team that does this ships LLM features faster than the team that doesn't, because they can change things without breaking things, and they know when something is actually better.

## Related skills

- `llm-application-engineering` for the wrappers your evals are testing
- `agent-design` for the agent-specific eval patterns
- `rag-architecture` for retrieval-specific metrics
- `prompt-injection-defense` for adversarial testing
- `human-in-the-loop-workflows` for the human-grader infrastructure
