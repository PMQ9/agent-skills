---
name: multi-agent-orchestration
description: Use this skill for designing systems where multiple LLM agents (or agent + sub-agents) collaborate — orchestrator/worker patterns, supervisor/router architectures, parallel agent execution, agent handoffs, agent-to-agent (A2A) communication, multi-agent debate, planner-executor splits, swarm patterns, and frameworks for multi-agent systems (LangGraph, CrewAI, AutoGen, OpenAI Swarm/Agents SDK, Anthropic's multi-agent research patterns, the A2A protocol). Trigger when the user asks about coordinating multiple agents, "should this be one agent or many," sub-agents, agent teams, parallel research agents, agent handoff, when a single agent's context is overflowing, or when designing systems where specialized agents handle different parts of a task. Compose with `agent-design` (for single-agent fundamentals) and `llm-cost-optimization` (multi-agent systems consume tokens fast).
---

# Multi-Agent Orchestration

A multi-agent system is one where two or more LLM-powered agents collaborate, each with its own context window, tools, and (usually) prompt. The right reason to build one is **separation of concerns** that a single agent can't handle in one context: parallel work that would otherwise serialize, specialized expertise that bloats one agent's prompt, or scopes that need different tool access.

The wrong reason — and the most common one — is "agents are cool." A multi-agent system costs more (10-15x token usage is normal vs. a single-agent equivalent for the same task; Anthropic's reported figures in their multi-agent research system), introduces failure modes single agents don't have (cascading errors, coordination bugs, infinite delegation loops), and is significantly harder to debug. Reach for it when the alternative is worse, not by default.

The companion skill `agent-design` covers single-agent fundamentals — the agent loop, tool design, context management, runaway control. This skill is about what changes when there's more than one.

## When to actually use multi-agent

Reach for multi-agent when at least one of these is true:

| Signal | Why it justifies the complexity |
|---|---|
| **Parallel research over many sources** | One agent reads 30 docs serially; ten agents each read 3 in parallel. The wall-clock saving is the point. |
| **Specialization with conflicting context** | A code-writing agent wants different system prompts, tools, and examples than a code-reviewing agent. Forcing them into one prompt produces a worse version of both. |
| **Different tool/permission scopes** | A "planner" agent shouldn't have file-write access; an "executor" agent shouldn't have access to PII the planner saw. |
| **Workflow with verifiable handoffs** | Researcher → writer → editor, where each phase has a clear "done" state and the next phase doesn't need the previous phase's reasoning. |
| **Distinct user roles in one system** | Customer agent, supervisor agent, internal-tools agent — each modeling a real role with real constraints. |

Reach for **a single agent with subagent tools** (which is what most "multi-agent" systems actually are under the hood) when:

- The orchestrator needs to coordinate work but the workers don't need to coordinate with each other.
- The work is fundamentally sequential (one step's output is the next's input).
- The task fits in one context window comfortably.

Reach for **a workflow** (deterministic chain, with LLM calls but no agentic decisioning) when:

- The steps are known in advance.
- Each step has a well-defined output schema.
- You don't actually need autonomous decision-making, just structured generation.

Workflows are cheaper, more predictable, and easier to debug than agents. Most things people build as agents would work better as workflows. Read [Anthropic's "Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents) — the workflow vs. agent distinction is foundational.

## Architectural patterns

### 1. Orchestrator-worker (the workhorse)

```
                ┌─── Worker A (research source 1)
Orchestrator ───┼─── Worker B (research source 2)
                └─── Worker C (research source 3)
```

The orchestrator decomposes the task, dispatches sub-tasks to workers, collects results, synthesizes. Workers are stateless from the orchestrator's perspective — each invocation gets the workers' output back and decides what's next.

This is the right default for parallelizable work. It's how Anthropic built the Research multi-agent system: a lead researcher spawns subagents to investigate different angles, each subagent returns a summary, the lead synthesizes.

Critical design points:

- **Workers are full LLM agents with their own context windows**, not just tool calls. That's the unlock — N parallel context windows extend the effective context the orchestrator has access to.
- **Workers return summaries, not full traces.** The orchestrator doesn't want or need each worker's intermediate reasoning; it wants the conclusions. This is also where token cost is controlled.
- **The orchestrator's prompt explains how to delegate well** — the system prompt teaches it to scope subtasks, not just dispatch them. Vague delegation produces vague worker output.
- **Workers don't communicate with each other** in this pattern. If they need to, you've moved to a different pattern.

Implementation: a `dispatch_subagent(task, context)` tool the orchestrator calls. Calls can run in parallel (this is the point — same as Claude's `Task` tool launching multiple agents at once).

### 2. Supervisor / router

```
                       ┌── Specialist A
User ─→ Supervisor ────┼── Specialist B
                       └── Specialist C
```

The supervisor classifies an incoming request and routes to the right specialist. The specialist handles the request end-to-end, optionally returning to the supervisor for follow-up routing.

Right when:

- Specialists are genuinely different (code agent, data agent, writing agent), each with different tools and prompts.
- Routing is the hard part, execution within a specialist is straightforward.

Often this can be simplified: the "supervisor" is just an LLM call that classifies, and then your code calls the right specialist. That's a workflow, not multi-agent — and it's simpler.

The supervisor becomes a real agent when it needs to make multi-turn routing decisions or do real work itself.

### 3. Handoff / swarm

```
Agent A ──hand off──→ Agent B ──hand off──→ Agent C
   ↑                                            │
   └────────────────hand off────────────────────┘
```

Agents pass control of the conversation to each other. The user is talking to "the system," but at any given moment one specific agent is responsible. Triage agent hands off to billing agent, billing agent hands off to refunds agent, etc.

OpenAI's Agents SDK (and the original `Swarm` library) is built around this pattern. Each agent can declare which other agents it can hand off to, and a tool call effects the handoff.

Right when:

- The interaction is conversational with the user.
- Different parts of the conversation are best served by different specialized agents.
- Each agent owns its turn and the next agent picks up cleanly.

Tricky parts:

- **State carryover.** When B takes over from A, what does B see? The whole conversation? A summary? Just the user's last message? Decide explicitly; don't rely on framework defaults.
- **Loops.** A → B → A → B can cycle. Add max-handoff limits and detect non-progress.

### 4. Planner-executor

```
Planner ──plan──→ Executor (loops over plan steps)
   ↑                            │
   └────re-plan if blocked──────┘
```

A planner agent produces a plan as structured output (a list of steps). An executor agent (or workflow) executes each step. If execution gets stuck, control returns to the planner with the failure context, and a revised plan is produced.

Right when:

- The task is long-horizon (many steps).
- Plans benefit from upfront thinking, but execution shouldn't re-think every step.
- Failures should trigger global re-planning, not local retry.

This pattern is what's behind a lot of "deep research" and "agentic coding" systems. Claude's interleaved thinking + plan tools edges into this — the model plans, then executes against the plan, with the option to revise.

### 5. Debate / multi-agent reasoning

```
Agent A (proposes) ←→ Agent B (critiques) ←→ Agent C (judges)
```

Multiple agents reason about the same problem, often with adversarial roles. Used for:

- Improving factuality (one agent generates, one critiques).
- Hard reasoning problems (multiple agents propose; aggregator picks).
- Self-consistency (run N times, vote).

The research literature is positive on this for some tasks (math, code review), mixed for others. In production it's expensive (multiple full agent calls per query) and worth using selectively for high-stakes decisions.

A simpler form is **LLM-as-judge** for evaluation, which doesn't require coordinated multi-agent — you generate with one prompt and score with another.

## The orchestrator's job, in detail

Most of the design effort in a multi-agent system is in the orchestrator. The workers are usually well-scoped agents you've already designed.

A good orchestrator does three things:

1. **Decomposes well.** Given the user's request, identifies the minimum set of subtasks. Doesn't over-decompose ("for a one-fact query, search 1 source, not 5"); doesn't under-decompose (a 50-source research task doesn't get one search).
2. **Dispatches with enough context.** Each subagent gets a clear task description, what's expected back, format, scope, and any context the orchestrator already gathered. "Research X" produces vague output; "Research X, focusing on data from after 2024, return 3-5 specific sources with quotes that address Y" produces useful output.
3. **Synthesizes.** Doesn't just concatenate worker outputs. Cross-references, identifies conflicts, fills gaps (possibly with another round of dispatching), and produces the final answer.

The orchestrator's system prompt has to teach all three. Examples in the prompt of "good decomposition vs bad decomposition" earn their tokens. This is the part that matters most for quality, and the part most teams underspecify.

## Context management across agents

In a single-agent system, context management is about not overflowing the window. In multi-agent, it's about **what each agent sees**, which is a design choice with real consequences.

Three rough strategies:

| Strategy | When | Trade-off |
|---|---|---|
| **Fresh context per worker** | Worker doesn't need the orchestrator's history. | Cheapest. Loses any nuance from orchestrator's reasoning. |
| **Summary forwarded** | Worker benefits from "here's what's been figured out so far." | Orchestrator pays to summarize; some lossy compression. |
| **Full shared history** | Tight collaboration with shared state needed. | Token-explosive; defeats some of the point of separating contexts. |

In Anthropic's multi-agent research system, the lead researcher passes a **task description** and **scope** to subagents — not the full lead's context. This is the right default for orchestrator-worker.

For handoff patterns, decide explicitly: does the next agent see the whole conversation, a structured handoff payload, or both?

A pattern that works well: **structured handoff messages**. Instead of "here's everything that happened," the handing-off agent emits a small JSON payload — `{ user_intent, key_facts, open_questions }` — and the next agent works from that. Forces the previous agent to articulate what matters; gives the next agent a clean slate.

## Communication and protocols

Most production multi-agent systems today are **single-process**: agents are functions, communication is function calls, state is in-memory. That's fine and often sufficient.

When agents need to live in different processes, services, or organizations, **A2A** (Agent-to-Agent) — Google's open protocol launched in April 2025, contributed to the Linux Foundation in mid-2025 — is the emerging standard. As of 2026, it has support from a broad set of vendors (Anthropic, AWS, Microsoft, ServiceNow, SAP among others) and is becoming the default for cross-vendor agent interop. It uses JSON-RPC over HTTP(S), with discovery via `AgentCards`. If your agents are crossing trust boundaries (your agent talking to a vendor's agent), A2A is the right plumbing to look at.

For agents within your own system, you don't need a wire protocol — direct function calls or your existing message bus is simpler.

The orthogonal piece is **MCP** (Model Context Protocol) — that's about agent-to-tool communication, not agent-to-agent. An agent calls tools (and other servers) via MCP; agents talk to each other via A2A or direct invocation. They compose: an A2A-exposed agent internally uses MCP to call its tools.

## Frameworks (2026 landscape)

You don't need a framework to build a multi-agent system — orchestrator-worker is twenty lines of code over a chat completions API. Frameworks earn their cost when you need their ergonomics for graph state, persistence, or tracing.

| Framework | Strengths | When |
|---|---|---|
| **LangGraph** | Explicit graph, durable execution, time-travel debugging, strong tracing via LangSmith. | Production workflows where observability and resumability matter. |
| **OpenAI Agents SDK** (Swarm successor) | Lightweight, handoff-first, minimal abstractions. | Conversational handoff systems, especially OpenAI-stack shops. |
| **CrewAI** | Role/goal abstractions, easy team composition. | Prototyping multi-agent ideas quickly; demos. Less customizable for production edge cases. |
| **AutoGen** (Microsoft) | Conversation-first, code execution agents, group chat patterns. | Research-style group conversation between agents. |
| **Anthropic Agents SDK** + Claude Agent SDK | Direct, file-system + bash + tool primitives. The pattern Claude Code uses. | Coding agents and Claude-stack work. |
| **Pydantic AI** | Type-safe, Python-idiomatic. | Python teams who want type safety and observability without a heavy graph abstraction. |
| **Hand-rolled** | Full control, no abstraction tax. | Most production systems should at least start here, then migrate if a framework's value clearly outweighs its complexity. |

A common mistake: **picking a framework before understanding the pattern you need.** Frameworks bias toward their preferred pattern. If you start in CrewAI and discover you need orchestrator-worker, you'll fight it; LangGraph would have been better.

## Cost and latency

Multi-agent systems are expensive. Anthropic's published data on their multi-agent research system shows ~15x the tokens of a single-agent baseline. That's not a bug — it's the cost of parallelism and specialization. But it means:

- **Don't multi-agent low-value queries.** Use simple workflows or single agents for the common case; reserve multi-agent for the queries where it matters.
- **Use cheaper models for workers.** A Haiku worker doing focused research, summarized for a Sonnet orchestrator, is a reasonable cost profile. The orchestrator does the heavy reasoning; workers do the legwork.
- **Cap worker count and depth.** A loop that spawns subagents that spawn subagents will burn through a budget. Hard limits at every level.
- **Cache shared system prompts** (prompt caching). The orchestrator's system prompt is reused across many spawn calls; caching it saves real money.
- **Limit per-worker token budgets.** Each worker has a max-tokens cap on its output and a max iteration count on its agent loop.

See `llm-cost-optimization` for the toolkit. Multi-agent makes most of it more important.

Latency: parallel agents are *faster* than serialized work but *slower than single-shot*. If wall-clock matters, parallel dispatch is the win; if user is waiting on one synchronous thing, single-agent is faster.

## Failure modes specific to multi-agent

Single-agent systems fail by hallucination, loop, or refusal. Multi-agent systems do all that **plus**:

### Cascading failure

Worker A produces wrong-but-plausible output. Worker B consumes it and produces output that's wrong-but-consistent-with-A. The orchestrator synthesizes plausible-but-wrong final output. The error is harder to detect because everything looks coherent.

Mitigations:

- **Verify worker output against ground truth** when possible (citations, source quotes, schemas).
- **Independence**: workers shouldn't see each other's outputs in research-style patterns. Each comes to its own conclusion; the orchestrator notices when they conflict.
- **Pessimism in the orchestrator**: prompt it to look for inconsistencies, not just synthesize.

### Coordination loops

A delegates to B, B asks A for clarification, A re-delegates the same question, B asks A again. Or A and B keep handing off to each other.

Mitigations:

- **Max handoff/dispatch counts** at every level. Hard limit.
- **Detect non-progress**: if successive states are similar, escalate or fail.
- **No bidirectional delegation** in orchestrator-worker. Workers report up; they don't dispatch to peers or back to the orchestrator.

### Lost context

The handing-off agent had a key piece of context that didn't survive the handoff. Now the next agent is producing answers based on a stale or incomplete picture.

Mitigations:

- Structured handoff payloads, schema-validated.
- Test handoffs explicitly: feed an agent only the handoff payload, see if it can do its job.
- Log every handoff with full context for post-hoc debugging.

### Specialization drift

The "code agent" is given a question that's really about deployment. It half-knows the answer and produces something half-right. A general agent would have noticed and asked.

Mitigations:

- Explicit out-of-scope handling in each specialist's prompt: "If the question is X, hand off to Y, don't try to answer."
- A clear escalation path back to a general agent or human.

### Untrusted communication / prompt injection

A worker that fetches web content can ingest a prompt-injection payload, then in its summary to the orchestrator, embed instructions. The orchestrator follows them. This is the supply chain attack of multi-agent.

Mitigations:

- Treat **all worker output as untrusted content** in the orchestrator. The orchestrator's system prompt explicitly says so.
- Use structured outputs from workers (JSON schemas) so freeform text doesn't propagate.
- Tool output rendered in a way that distinguishes "this is what we retrieved" from "this is an instruction."
- See the `prompt-injection-defense` skill for the full picture.

## Observability

Multi-agent systems are nearly impossible to debug without good tracing.

The minimum:

- **A trace per top-level invocation** that captures every agent call, tool call, prompt, and response.
- **Parent-child relationships** between orchestrator and workers, preserved.
- **Token counts** per agent and per call.
- **Latency** per agent and end-to-end.

Tools that do this well: LangSmith (LangGraph), Langfuse, Arize Phoenix, Helicone, Weights & Biases Weave, OpenTelemetry GenAI semantic conventions for DIY. Pick one early. Trying to add tracing after the fact when you're trying to debug a misbehaving system is its own struggle.

For evals (does the new orchestrator prompt produce better outputs?), see `llm-evaluation`. The complication for multi-agent: you often need to evaluate the *whole system* end-to-end, not individual agents in isolation, because emergent behaviors come from coordination.

## Human in the loop

Multi-agent systems are good candidates for HITL gates. Some natural points:

- **Plan approval** in planner-executor: human reviews the plan before execution.
- **High-stakes tool calls** behind approval: writing to the database, sending emails, spending money.
- **Synthesis review** before delivering to the user.
- **Disagreement escalation**: when two agents conflict and the orchestrator can't resolve, ask a human.

See `human-in-the-loop-workflows` for the design space. Multi-agent systems benefit disproportionately from HITL because their failure modes are subtler.

## A reasonable orchestrator-worker skeleton

Pseudocode for the most common pattern:

```python
def orchestrator(user_query: str) -> str:
    # Single LLM call with tools that include `dispatch_subagent`
    # The model plans, dispatches workers in parallel, synthesizes.

    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(MAX_ORCHESTRATOR_ITERATIONS):
        response = model.complete(
            messages=messages,
            tools=[dispatch_subagent_tool, web_search_tool, ...],
        )

        if response.stop_reason == "end_turn":
            return response.text

        # Execute tool calls, possibly in parallel
        tool_results = execute_tool_calls_parallel(response.tool_calls)
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    raise OrchestratorBudgetExceeded()


def dispatch_subagent(task: str, scope: str) -> str:
    """Tool the orchestrator calls. Each call is a full agent loop."""
    messages = [
        {"role": "system", "content": SUBAGENT_SYSTEM_PROMPT},
        {"role": "user", "content": format_subagent_task(task, scope)},
    ]

    for iteration in range(MAX_SUBAGENT_ITERATIONS):
        response = model.complete(
            messages=messages,
            tools=[search_tool, fetch_tool, ...],   # narrower toolset
        )
        if response.stop_reason == "end_turn":
            return summarize_for_orchestrator(response.text)
        tool_results = execute_tool_calls(response.tool_calls)
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return f"Subagent budget exceeded. Partial findings: {best_so_far(messages)}"
```

The shape worth noting:

- The orchestrator **doesn't see the subagent's full message history**. It gets `summarize_for_orchestrator(...)` — a focused summary.
- Subagents have a **narrower toolset** than the orchestrator.
- Both have **iteration budgets**. Both have **failure modes that produce a partial answer**, not silence.
- Parallel dispatch happens at the tool-execution layer, not in the model. The model emits multiple tool calls; you execute them concurrently.

## Common anti-patterns

- **Multi-agent for problems a single agent solves**, because the framework demo had multiple agents.
- **Workers that need to talk to each other**. Now you've got a coordination problem and N(N-1) interaction surfaces. Restructure to orchestrator-worker.
- **Orchestrator dumps all worker outputs verbatim** to the user. The orchestrator should *synthesize*, not concatenate.
- **No iteration limits anywhere.** A single bug in delegation logic burns thousands of dollars overnight.
- **Frameworks chosen before patterns.** The framework's preferred pattern then dictates architecture.
- **Workers too smart.** A Sonnet/Opus subagent doing trivial summarization is a cost mistake. Match model to job.
- **Workers too dumb.** A Haiku subagent doing complex reasoning produces bad input the orchestrator trusts. Match model to job.
- **No tracing.** When the system misbehaves, nobody can see why.
- **Trusting worker output.** Anything a worker fetches from the internet is potentially adversarial. Treat it accordingly.
- **Designing the system before stating the goal.** What does success look like? What's the eval? Build that first; let the architecture follow.
- **Sub-sub-agents that recursively spawn more agents.** A practical depth limit (1-2 levels max) prevents fractal cost explosion.
- **Identical agents working in parallel.** That's just a load balancer, not multi-agent. If the agents are interchangeable, a single agent calling tools in parallel is simpler.
- **Coordination via shared mutable state**. Agents racing to write to the same store. If you need shared state, use a coordinator (the orchestrator), not a free-for-all.

## When to back off to single-agent

Periodically interrogate a multi-agent design:

- Could a workflow do this? (Workflows are deterministic and cheap.)
- Could a single agent with subagent tools do this? (One context, parallel work.)
- Are the agents actually different, or are they just different prompts on the same underlying capability?
- Is the orchestration logic itself worth its tokens?

The mature path on most projects is: prototype with a single agent, hit a clear scaling wall (context, specialization, parallelism), introduce orchestrator-worker for that specific wall, and stop there. Most multi-agent systems do not need to be more elaborate than that.
