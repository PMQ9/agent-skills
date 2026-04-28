---
name: agent-design
description: How to design LLM-powered agents — when to use an agent at all versus a simpler workflow, how to structure tools and the agent loop, manage context across long-running tasks, prevent runaway loops and cost blowups, design for failure recovery, and build agents that can be tested and trusted. Use this skill whenever the task involves building something that calls tools in a loop, autonomous task execution, multi-step reasoning systems, "AI assistants" that take actions, planner-executor architectures, or any system where an LLM controls control flow rather than just generating text. Trigger when someone says "agent," "autonomous," "tool use," "function calling loop," "AI assistant that can do things," or describes a problem the obvious solution to which is "let the LLM call tools until it's done."
---

# Agent Design

The defining property of an agent is that the LLM controls the loop. In a workflow, the code calls the model at known points; in an agent, the model decides when to act, when to call a tool, and when to stop. That shift — from code-driven to model-driven control flow — is what makes agents powerful and what makes them dangerous to build naively.

## First, decide if you actually need an agent

Most "agent" projects should not be agents. The first question is whether the problem decomposes into known steps or whether the steps must be discovered at runtime.

If you can write the steps as a flowchart, you do not need an agent. You need a workflow. Workflows are predictable, debuggable, and cheap. The agent option costs more, fails more strangely, and is harder to evaluate. Pay that cost only when the work demands it.

Workflow patterns that solve most LLM problems and are *not* agents:

- **Prompt chaining.** Output of step 1 feeds step 2 feeds step 3, with optional gates between steps. Use when the task decomposes into a fixed sequence.
- **Routing.** Classify the input, then dispatch to a specialized prompt. Use when distinct subtasks benefit from distinct prompts/models.
- **Parallelization.** Fan out to N parallel calls, then aggregate. Use for independent subproblems (per-document analysis, per-section drafting) or for voting/ensembling.
- **Orchestrator-workers.** A planner LLM dynamically generates subtasks; worker LLMs execute them; the orchestrator integrates results. This is *almost* an agent — the difference is the orchestrator runs once per task rather than looping over feedback.
- **Evaluator-optimizer.** One LLM produces, another critiques, the producer revises until the critic is satisfied. Bounded loop, well-scoped.

You need a true agent (LLM-controlled loop with tool use) when:

- The set of steps cannot be enumerated in advance.
- Success requires interaction with a stateful environment (a codebase, a browser, a filesystem) where each step's result determines the next.
- The task has a clear success signal but unclear path to it (think: "fix this failing test" or "find the bug").

If none of those apply, build a workflow. The skill `llm-application-engineering` covers most workflow patterns.

## The agent loop

A minimum viable agent looks like this:

```
loop:
    response = model(messages, tools)
    if response.is_stop:
        return response.content
    for tool_call in response.tool_calls:
        result = execute(tool_call)
        messages.append(tool_call)
        messages.append(result)
```

Everything else — planners, scratchpads, reflection, sub-agents — is layered on top of this loop. The loop itself is simple. What's hard is making it *terminate well* and *fail well*.

## Designing the tool surface

The tools you give an agent are its API to the world. Design them like you would design a public API for human developers, because the LLM is, in effect, a developer reading your docs at runtime.

**Naming.** Tool names should describe the action and its scope. `search_codebase` beats `search`; `send_email_to_customer` beats `send_email`. The model uses the name as a primary signal.

**Descriptions.** Write the description as if explaining to a junior engineer who will use the tool exactly once. Include: what it does, when to use it, when *not* to use it, examples, common mistakes. A long, specific description outperforms a short one consistently.

**Parameters.** Required fields should be required in the schema. Optional fields should have sensible defaults documented in the description. Avoid free-text parameters where an enum would do — `priority: "low" | "medium" | "high"` is enforceable, `priority: string` is a wish.

**Error messages from tools matter as much as success messages.** When a tool fails, return a structured error the model can act on: what went wrong, why, what to try instead. `"Error: file not found"` is barely useful. `"Error: file not found at path 'foo.py'. The directory contains: bar.py, baz.py. Did you mean one of those?"` lets the model recover.

**Idempotency and reversibility.** Mark tools that have side effects clearly. For destructive actions (deletes, sends, payments), make the agent confirm before executing — either with a human-in-the-loop step or with a two-phase commit (`prepare_delete` returns a token; `confirm_delete(token)` actually deletes).

**Granularity.** Avoid a single mega-tool with twelve modes selected by a string parameter. Models confuse modes. Prefer N focused tools to one swiss-army tool. The exception: when the tools share enough state that splitting them produces redundant calls — then keep them together but separate the *parameters* clearly.

A useful heuristic: a tool surface is well-designed if a new engineer reading just the tool descriptions can predict what the agent will do for a given task. If they can't, the model can't either.

## Context management

The agent loop appends to a message history every iteration. Without intervention, the context grows linearly with the trajectory length, and three things go wrong:

1. Cost grows quadratically (each call processes the full history).
2. Latency grows linearly.
3. Quality degrades — long contexts make models lose focus, especially on the middle of the context ("lost in the middle").

Strategies, in order of preference:

- **Tool result truncation.** When a tool returns a 50-page document, the model rarely needs all 50 pages. Truncate to the most relevant section, or store the full result keyed by an ID and return a summary plus the ID.
- **Summarization checkpoints.** Periodically replace older history with a generated summary. This works well when older steps are reference material, less well when fine details matter.
- **Sub-agents / handoffs.** Spawn a sub-agent with a fresh context for a contained subtask, return only its result. The parent never sees the sub-agent's intermediate steps. This is the cleanest pattern for long horizons, but adds complexity.
- **External memory.** Write notes/state to a scratchpad file or a structured store, and let the agent read back what it needs. Keeps the context small but adds tool calls.
- **Sliding window with pinning.** Keep the system prompt and the most recent N turns; drop the middle. Works for chat-style agents where recent context dominates.

The right strategy depends on the task. A code-editing agent benefits from external memory (the file tree, the diff stack); a customer support agent benefits from summarization; a research agent benefits from sub-agents per topic.

## Termination

Agents that don't know when to stop will loop forever, burn budget, and emit hallucinated "successes." Engineer termination as deliberately as you engineer the loop:

- **Hard step limit.** Always set a maximum iteration count. Pick a number 2-3x the median trajectory length. When hit, stop and surface the partial result with a clear "iteration limit reached" status.
- **Hard cost limit.** Track tokens spent and stop when a budget is exceeded. Critical for production agents serving end users.
- **Hard wall-clock limit.** Long-running agents need timeouts. The agent doesn't know the user gave up 20 minutes ago.
- **Stop signal in the schema.** Give the model an explicit way to declare "done": a `done` tool, or a structured response with a `finished: true` field. Models terminate more reliably when termination is a first-class action, not the absence of a tool call.
- **Loop detection.** Track repeated tool calls with identical arguments. If the model called `read_file('foo.py')` four times in a row, it's stuck. Either intervene programmatically or surface a "you appear to be looping" message back to the model.

A useful invariant: the agent system, not the model, decides when to terminate. The model can request termination, but the runtime enforces the limits. This is the same principle as a watchdog timer — never trust the loop to police itself.

## Planning

For non-trivial tasks, generating a plan before acting improves outcomes. Two patterns:

**Plan-then-execute.** The model produces a structured plan as its first action, then executes against the plan, updating it as needed. Works well when the task is decomposable up front.

**ReAct-style interleaved reasoning.** The model alternates "thought" and "action" steps. Each iteration produces a thought (free-form reasoning) followed by a tool call. Works well when the path is genuinely uncertain.

Modern reasoning models often subsume the ReAct pattern internally — they think before each tool call without you having to scaffold it. For these models, the explicit thought/action split adds little. For non-reasoning models, the scaffold helps.

Anti-pattern: forcing both. If the model is producing extensive reasoning *and* you're asking it for an explicit plan *and* you've added a scratchpad tool, you've triple-paid for the same thing. Pick one.

## Failure recovery

Agents fail. The questions are: how loudly, how recoverably, how visibly?

- **Tool failures.** Return structured errors (see above). The agent should be able to retry, fall back to alternatives, or escalate — not just propagate the error.
- **Model failures.** API errors, refusals, validation errors. Wrap the model call (see `llm-application-engineering`) so transient failures retry transparently.
- **Plan failures.** The model's plan was wrong. Building self-correction into the loop helps: a critic step ("does this result match what we wanted?") that can trigger a retry with feedback.
- **Catastrophic failures.** Out of budget, can't make progress, hitting a permission wall. Bail out cleanly, save state, escalate to a human. See `human-in-the-loop-workflows`.

Build a *resume* path for any agent that runs longer than a minute. Save state (messages, scratchpad, plan) at checkpoints. When something fails, the user should be able to resume rather than restart from scratch.

## Multi-agent and sub-agent systems

Spawning sub-agents is sometimes the right answer and often a complexity trap. It's right when:

- The subtask has a clean interface (input → output) and benefits from a fresh context.
- The subtask uses different tools than the parent (a research sub-agent has a browser; the parent doesn't need it).
- The subtask can run in parallel with siblings (fan-out research, per-file refactors).

It's wrong when:

- The subtask needs constant feedback from the parent. You'll spend more on coordination than on work.
- The "agents" are really just prompt chains in disguise. A linear sequence does not benefit from being modeled as agents talking to each other.
- You're using multi-agent because it sounds more sophisticated. It costs more, fails in stranger ways, and is harder to evaluate.

A useful rule: model the simplest version first (single agent, all tools). Add a sub-agent only when you have a concrete reason — measured cost, measured quality, or a clean separation that makes testing easier.

## Memory beyond the trajectory

For agents that operate over many sessions or many users, you need memory that outlives a single trajectory:

- **Conversation memory.** Summary of past conversations, preferences, prior commitments. Usually written by a separate "memory writer" pass after each session.
- **Procedural memory.** Skills/playbooks the agent has learned. A library of "if X, do Y" patterns surfaced via retrieval. Updated when an interaction succeeds via a novel approach.
- **Factual memory.** Stable facts about the user, the domain, the environment. Updated explicitly or via a verifier step.

The hard part is *forgetting*: which entries are stale, which were wrong, which were tactical for one session and shouldn't carry forward. A memory system without a deliberate forgetting policy degrades over time. Plan deletion and TTLs alongside writes.

## Observability for agents

Beyond per-call traces (see `llm-application-engineering`), agents need trajectory-level observability:

- **Full trajectory replay.** For any failed or flagged session, you should be able to view the entire message history, every tool call, every result. Make this a first-class debugging UI, not a log file.
- **Step-level metrics.** Latency, tokens, cost, error rate per step.
- **Trajectory metrics.** Success rate, mean/p99 trajectory length, cost per trajectory, percentage that hit step/cost limits.
- **Tool-level metrics.** How often is each tool called? Which tools fail most? Which tools are *never* called (and probably shouldn't exist)?
- **Termination cause distribution.** What fraction terminate because the model said "done" vs. hit step limit vs. hit cost limit vs. errored out? Shifts here are early warning signs.

A good agent observability stack lets you ask "show me all the trajectories from yesterday that succeeded but cost more than $1" and get an answer in seconds. If you can't, you'll miss regressions.

## Evaluating agents

This is harder than evaluating single LLM calls. See the `llm-evaluation` skill, but a few agent-specific notes:

- Evaluate end-to-end (did the agent complete the task?) and step-by-step (did it pick the right tool? did it recover from the error?). End-to-end is the bottom line; step-by-step diagnoses regressions.
- Use real environments where possible. Sandboxed mock environments hide failure modes. A code agent should be evaluated on a real (containerized) codebase, not a mock filesystem.
- Track variance. The same prompt and same tools produce different trajectories. Run each eval case multiple times before declaring a regression.
- Look at *trajectories*, not just outcomes. Two agents with the same success rate can have wildly different cost, latency, and behavior. The trajectory tells you which one to ship.

## Anti-patterns

**The agent that should be a workflow.** Three known steps in a known order, modeled as a freewheeling agent loop. Pays the agent tax for no benefit. Refactor to a chain.

**The infinite tool surface.** 40 tools given to the agent because "more tools means more capability." The model gets confused, picks wrong tools, ignores the tools you wanted. Trim ruthlessly.

**The unmonitored loop.** No step limit, no cost limit, no termination logging. Will eventually run for hours and produce a five-figure bill.

**The mute agent.** No streaming, no progress events. The user sees a spinner for two minutes and assumes it crashed. Surface progress as it happens.

**The "agent" that's actually a single function call.** The model is given tools but the task is so simple it makes one tool call and stops. You're paying agent infrastructure cost for what should be a direct function dispatch.

**The plan-the-plan.** Multiple meta-layers of planning ("plan the plan to plan the task") that consume context without producing action. One layer of planning is enough for almost everything.

**The do-everything tool.** A single `execute(action: str, params: dict)` tool that internally dispatches to twenty subactions. Loses all the schema-level guidance the model needs. Split it up.

## The shape of a production agent

A production-ready agent has, at minimum:

- A bounded loop with hard step, cost, and time limits.
- A tested tool surface with clear schemas, descriptions, and error messages.
- Context management appropriate to expected trajectory length.
- Streaming/progress events for interactive use.
- Full trajectory tracing in observability.
- Resume/checkpoint support for long-running cases.
- Eval suite that exercises real environments.
- A human escalation path for failures and high-risk actions.

Anything less is a demo. That's fine for a demo. It's not fine for production.

## Related skills

- `llm-application-engineering` for the per-call infrastructure agents are built on
- `mcp-server-design` for the protocol that exposes tools to agents
- `prompt-injection-defense` — agents that take actions are the highest-stakes injection target
- `human-in-the-loop-workflows` for when and how to insert human review
- `llm-evaluation` for the discipline that tells you whether the agent works
