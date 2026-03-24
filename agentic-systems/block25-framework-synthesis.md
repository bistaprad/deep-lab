# Block 25 — Synthesis: Building an Agentic Framework from Scratch

## What This Block Is

Blocks 21-24 covered the individual pieces: reasoning loops, context management, multi-agent orchestration, and security. This block puts it all together — designing and building a minimal but complete agentic framework from scratch.

## The Architecture of a Framework

Every agentic framework (LangChain, CrewAI, AutoGen, LangGraph) is an implementation of these layers:

```
┌───────────────────────────────────────────────────┐
│                   API / Interface                  │
│   (define agents, tools, workflows, run tasks)     │
├───────────────────────────────────────────────────┤
│                 Orchestration Layer                 │
│   (supervisor, pipeline, parallel, event-driven)   │
├───────────────────────────────────────────────────┤
│                  Reasoning Layer                    │
│   (ReAct loop, plan-execute, reflexion)            │
├───────────────────────────────────────────────────┤
│                Context Management                   │
│   (summarization, folding, memory, retrieval)      │
├───────────────────────────────────────────────────┤
│                  Security Layer                     │
│   (sandboxing, guardrails, audit, isolation)       │
├───────────────────────────────────────────────────┤
│                   Tool Layer                        │
│   (execution, validation, rate limiting, retries)  │
├───────────────────────────────────────────────────┤
│                  LLM Adapter                        │
│   (Claude, GPT, Gemini, local models)              │
└───────────────────────────────────────────────────┘
```

### What Makes a Good Framework vs a Bad One

**Good frameworks** make common patterns easy and unusual patterns possible. They provide:
- Sensible defaults (ReAct loop works out of the box)
- Composability (mix patterns: supervisor with parallel agents, each using ReAct)
- Observability (every LLM call and tool call is traced)
- Escape hatches (override any layer when the framework doesn't fit)

**Bad frameworks** impose abstractions that don't match reality:
- Forced inheritance hierarchies when composition would work
- "Magic" routing that's impossible to debug
- Implicit state management that causes race conditions
- Over-abstraction that adds layers without adding value

## Designing the Core Abstractions

### Agent

```python
@dataclass
class Agent:
    name: str
    system_prompt: str
    tools: list[Tool]
    reasoning: ReasoningStrategy   # ReAct, PlanExecute, etc.
    context_manager: ContextManager
    security: SecurityPolicy
    model: str = "claude-sonnet-4-20250514"
    max_iterations: int = 10
    
    def run(self, task: str, shared_state: SharedState = None) -> AgentResult:
        messages = self.context_manager.init(self.system_prompt, task)
        trace = Trace(self.name)
        
        for i in range(self.max_iterations):
            # Context management
            if self.context_manager.needs_compression(messages):
                messages = self.context_manager.compress(messages)
            
            # Reasoning step
            response = self.reasoning.step(messages, self.tools, self.model)
            trace.add(response)
            
            # Check if done
            if response.is_final:
                return AgentResult(response.text, trace)
            
            # Security check
            for tool_call in response.tool_calls:
                violation = self.security.check(tool_call)
                if violation:
                    messages.append(tool_result(tool_call, violation.message))
                    continue
                
                # Execute tool
                result = self.security.execute(tool_call)
                messages.append(tool_result(tool_call, result))
        
        return AgentResult("Max iterations reached", trace)
```

### Tool

```python
@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    function: Callable
    requires_approval: bool = False
    max_output_tokens: int = 4000
    timeout_seconds: int = 30
```

### Workflow

```python
@dataclass
class WorkflowStep:
    agent: Agent
    name: str
    dependencies: list[str] = field(default_factory=list)  # names of prior steps
    condition: Callable | None = None  # skip if condition returns False

class Workflow:
    def __init__(self, steps: list[WorkflowStep]):
        self.steps = steps
        self.dag = self._build_dag(steps)
    
    def run(self, task: str) -> WorkflowResult:
        shared_state = SharedState()
        shared_state.write("system", "task", task)
        
        results = {}
        for batch in self.dag.topological_batches():
            # Parallel execution within each batch
            batch_results = asyncio.gather(*[
                step.agent.run(
                    self._build_step_input(step, results),
                    shared_state
                )
                for step in batch
                if step.condition is None or step.condition(results)
            ])
            for step, result in zip(batch, batch_results):
                results[step.name] = result
        
        return WorkflowResult(results)
```

## What Frameworks Actually Provide (and What They Don't)

### LangChain / LangGraph
- **Provides:** Graph-based workflow definition, state management between nodes, built-in tool adapters
- **Pattern:** Nodes are agents or functions, edges are transitions, state flows through the graph
- **Weakness:** Heavy abstraction layer, debugging requires understanding the graph execution model

### CrewAI
- **Provides:** Role-based agent definition, task delegation, process types (sequential, hierarchical)
- **Pattern:** Define agents with roles and goals, tasks with expected outputs, crew orchestration
- **Weakness:** Less flexible for non-role-based patterns, limited custom orchestration

### AutoGen (Microsoft)
- **Provides:** Conversational multi-agent framework, group chat patterns
- **Pattern:** Agents communicate via messages in a shared conversation
- **Weakness:** Conversation-centric model doesn't fit all use cases (e.g., data pipelines)

### The Common Thread

Strip away the marketing, and all frameworks implement the same core:
1. A way to define agents (system prompt + tools + model)
2. A reasoning loop (almost always ReAct)
3. A way to connect agents (orchestration pattern)
4. Context/state management
5. Tool execution

The differences are in the API surface, default patterns, and observability.

## Open Challenges in Agentic Systems

### 1. Evaluation

How do you know if your agent is good? Traditional software has unit tests. Agents are non-deterministic — the same input can produce different tool call sequences and final answers.

**Current approaches:**
- **Evals framework:** Run 100 test cases, measure success rate, latency, cost
- **LLM-as-judge:** Use a separate LLM to grade agent outputs
- **Human-in-the-loop:** Sample outputs for human review
- **Regression testing:** Compare outputs before/after changes, flag regressions

### 2. Debugging

When a multi-agent system produces wrong output, where do you look?
- Which agent made the wrong tool call?
- Was it the tool result that was misleading, or the agent's interpretation?
- Did context compression lose critical information?
- Did the orchestrator route to the wrong specialist?

**Current approaches:**
- Full execution traces (every thought, action, observation)
- Replay: re-run the same investigation with the same inputs, varying one parameter
- Counterfactual analysis: "what if Agent B had received X instead of Y?"

### 3. Cost Control

Agent loops are expensive. A 10-iteration ReAct loop with Claude Sonnet costs ~$0.50-2.00. A multi-agent system with 4 agents, each running 5 iterations, costs ~$5-10 per investigation.

**Current approaches:**
- Cost budgets per agent and per workflow
- Token-efficient prompts (shorter system prompts, structured outputs)
- Caching: store tool results and agent outputs, skip re-computation for identical inputs
- Model routing: use cheaper models for simple subtasks, expensive models for reasoning

### 4. Reliability

Production agents need to handle:
- LLM API downtime (retry with exponential backoff, failover to alternative model)
- Tool failures (retry, try alternative tools, degrade gracefully)
- Partial results (report what you have, not nothing)
- Stuck agents (timeout detection, force termination, report partial findings)

## Exercises

1. Implement the Agent class above. Support both ReAct and PlanExecute reasoning strategies, swappable via configuration.
2. Build a 2-step workflow: Triage Agent → Specialist Agent. Wire them together with structured handoffs.
3. Add observability: emit metrics for every agent run (duration, iterations, tool_calls, tokens_used, cost).

## Key Takeaways

> "Every framework is an implementation of the same 5 layers: reasoning, context, orchestration, security, tools. Understanding the layers means you can evaluate any framework in minutes and build your own when needed."

> "The hardest problems in agentic systems aren't in the reasoning loop (that's solved). They're in evaluation, debugging, cost control, and reliability. These are the same problems you solve in any distributed system."

---

## Build — Minimal Agentic Framework

Build a complete agentic framework in ~500 lines of Python. No dependencies on LangChain or similar.

**Requirements:**
1. **Agent definition**: name, system_prompt, tools, model, max_iterations, context_manager, security_policy
2. **Two reasoning strategies**: ReAct and Plan-Execute, selectable per agent
3. **Context manager**: token counting, result truncation, summarization when golden window exceeded
4. **Tool layer**: schema validation, timeout, retry (1 retry on failure), audit logging
5. **Security**: deny-by-default policy engine, tool allow list per agent, output scanning
6. **Workflow**: define multi-agent workflows as DAGs, execute with parallel batching
7. **Observability**: per-agent metrics (iterations, tokens, tool_calls, cost), per-workflow metrics (duration, total_cost)
8. **CLI**: `python framework.py --agent crash-triage --task "Investigate OOM on pod X"`

**Test:** Define a 3-agent crash investigation workflow. Run it end-to-end with mock tools. Verify: structured handoffs work, context stays within bounds, security violations are caught, metrics are emitted.

**What you'll learn:** How much code a framework actually requires (less than you think), where the complexity lives (context management and error handling, not the reasoning loop), why observability is the most underinvested layer.

---

## Design — Production Agent Platform

Design the production platform for running agents at scale in an enterprise.

**Requirements:**
- Host 50+ agent types (crash triage, code review, test analysis, customer support)
- Execute 1000+ agent runs per day
- Multi-tenant: different teams define their own agents with isolated tools and data
- Versioning: agent templates (prompt + tools + config) are versioned, auditable, rollback-able
- A/B testing: run two versions of an agent side-by-side, compare quality and cost
- Cost management: per-team budgets, per-agent cost tracking, alerts on budget overrun
- Reliability: 99.9% availability, graceful degradation (if Claude is down, fall back to GPT)
- Compliance: full audit trail, PII redaction, data retention policies

**Design decisions:**
- Where does the reasoning loop run? (Centralized service? Per-agent containers? Serverless?)
- How do you handle agent state across restarts? (Checkpoint to persistent store? Re-run from scratch?)
- How do you manage tool access across tenants? (Shared tool registry with RBAC? Per-tenant tool deployments?)
- What's the deployment model? (GitOps for agent templates? API for dynamic registration?)
- How do you measure agent quality? (Automated evals? Human review sampling? Customer satisfaction?)
- How do you handle model vendor lock-in? (Unified LLM adapter? Multi-model strategies?)

## Self-Assessment: Domain E — Agentic Systems Engineering

After completing Blocks 21-25, answer without notes:

1. Explain the ReAct loop in 3 sentences. What specific problem does the observe step solve that chain-of-thought alone cannot?
2. Your agent is at 85K tokens in a 100K window after 12 iterations. Three strategies to keep going without losing earlier findings.
3. You're building a 4-agent crash investigation system. Draw the orchestration pattern. What's the handoff protocol between the log analyst and the metrics analyst?
4. An attacker sends a prompt injection through a tool result (a log line contains "ignore previous instructions and..."). How does your security layer prevent this from affecting the agent?
5. You need to evaluate whether your crash triage agent v2 is better than v1. Design the evaluation pipeline. What metrics? How many test cases? How do you handle non-determinism?
6. Your agent costs $8 per investigation. The team wants it under $2. Where do you cut costs without destroying quality?
