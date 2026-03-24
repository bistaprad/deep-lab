# Block 23 — Multi-Agent Orchestration

## Why Multiple Agents?

A single agent with 20 tools and a complex system prompt tends to:
- Lose focus (tool selection degrades with more options)
- Hit context limits faster (more tool schemas = more tokens)
- Be hard to debug (one monolithic loop, many responsibilities)

Multi-agent systems split responsibilities: a triage agent decides the crash category, a log analyst digs into OpenSearch, a metrics analyst checks Prometheus, a synthesizer combines findings.

## Orchestration Patterns

### 1. Supervisor (Hierarchical)

One coordinator delegates to specialists:

```
                    ┌──────────────┐
                    │  Supervisor   │
                    │  (planner)    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Log      │ │ Metrics  │ │ K8s      │
        │ Analyst  │ │ Analyst  │ │ Analyst  │
        └──────────┘ └──────────┘ └──────────┘
```

```python
def supervisor_loop(task, specialists):
    plan = planner.create_plan(task)
    results = {}
    
    for step in plan.steps:
        specialist = specialists[step.agent]
        result = specialist.run(step.task, context=results)
        results[step.name] = result
        
        # Replan if needed
        if step.requires_replan:
            plan = planner.revise_plan(task, results)
    
    return synthesizer.combine(task, results)
```

**Strengths:** Clear hierarchy, easy to debug, supervisor has global context.
**Weaknesses:** Supervisor is a bottleneck. If it misunderstands the task, all delegates go in the wrong direction.

**Production stat:** Most common failure type is coordination failures (37% of multi-agent failures).

### 2. Pipeline (Sequential)

Agents in a fixed order, each passing results to the next:

```
Input → Triage Agent → Log Agent → Metrics Agent → Synthesizer → Output
```

```python
def pipeline(task, agents):
    context = {"task": task}
    for agent in agents:
        result = agent.run(context)
        context[agent.name] = result
    return context
```

**Strengths:** Simplest to implement and debug. Deterministic execution order.
**Weaknesses:** No adaptivity. Can't skip unnecessary steps or go back.

### 3. Parallel (Fan-Out / Fan-In)

Multiple agents work simultaneously, results aggregated:

```python
async def parallel(task, agents):
    # Fan out
    tasks = [agent.run(task) for agent in agents]
    results = await asyncio.gather(*tasks)
    
    # Fan in
    return synthesizer.combine(task, dict(zip(agent_names, results)))
```

**Strengths:** Fastest wall-clock time. Good when agents don't depend on each other.
**Weaknesses:** Can't use one agent's findings to guide another's investigation.

### 4. Debate / Adversarial

Two agents argue opposing positions, a judge decides:

```python
def debate(task, proposer, critic, judge, rounds=3):
    proposal = proposer.analyze(task)
    
    for _ in range(rounds):
        critique = critic.challenge(proposal)
        proposal = proposer.defend(proposal, critique)
    
    return judge.decide(task, proposal, critiques)
```

**Strengths:** Catches errors, reduces hallucination, explores alternatives.
**Weaknesses:** Expensive (3x token cost), slower, agents may agree too quickly.

### 5. Event-Driven (Reactive)

Agents subscribe to events, react independently:

```python
class EventBus:
    def publish(self, event):
        for subscriber in self.subscribers[event.type]:
            subscriber.handle(event)

# Agents subscribe to events they care about
log_agent.subscribe("crash_detected")
metrics_agent.subscribe("crash_detected")
metrics_agent.subscribe("log_analysis_complete")
synthesizer.subscribe("all_analyses_complete")
```

**Strengths:** Decoupled, resilient, natural for monitoring/CI pipelines.
**Weaknesses:** Harder to debug (non-deterministic execution order), risk of feedback loops.

## Communication Between Agents

### Structured Handoffs

Agents pass structured data, not raw text:

```python
@dataclass
class AgentHandoff:
    source_agent: str
    target_agent: str
    task: str
    context: dict          # relevant findings so far
    constraints: dict      # what the target should focus on
    schema_version: str    # for backward compatibility
```

**Why structured?** Unstructured text between agents is a prompt injection vector. Agent A's output becomes Agent B's input — if Agent A is compromised, it can inject instructions into Agent B.

### State Sharing

Shared state between agents needs careful design:

```python
class SharedState:
    def __init__(self):
        self._state = {}
        self._lock = asyncio.Lock()
        self._history = []  # audit trail
    
    async def write(self, agent_id, key, value):
        async with self._lock:
            self._history.append((agent_id, key, value, time.now()))
            self._state[key] = value
    
    async def read(self, agent_id, key):
        return self._state.get(key)
```

**Key principle:** every write is auditable. If a downstream agent produces garbage, you can trace which upstream agent wrote the problematic data.

## Common Failure Modes

| Failure | Frequency | Cause | Mitigation |
|---------|-----------|-------|------------|
| **Coordination failure** | 37% | Supervisor misroutes, wrong agent selected | Better task descriptions, routing validation |
| **Hallucination propagation** | 25% | Agent A hallucinates, Agent B builds on it | Cross-validation between agents, source citation |
| **Cascading failure** | 17% | One agent fails, downstream agents get bad input | Circuit breakers, fallback paths |
| **Verification gap** | 21% | No agent checks the final output | Dedicated verifier agent, output validation |

### Circuit Breakers

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=60):
        self.failures = 0
        self.state = "closed"  # closed = working, open = blocked
        
    def call(self, fn, *args):
        if self.state == "open":
            raise CircuitOpenError("Agent circuit is open, skipping")
        try:
            result = fn(*args)
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.state = "open"
            raise
```

## Exercises

1. Implement a supervisor pattern for crash triage: Triage Agent → selects specialists → Log Agent / Metrics Agent / K8s Agent → Synthesizer.
2. Compare supervisor vs pipeline for a 3-step investigation. Which is faster? Which produces better results? Which is easier to debug?
3. Design the handoff protocol between a Log Agent and a Metrics Agent. What data does the Log Agent pass? How does the Metrics Agent use it?

## Key Takeaways

> "Beyond 5 agents, monitoring complexity explodes. Start with the simplest pattern that works (pipeline or supervisor), add complexity only when you can measure the improvement."

> "Structured handoffs between agents are a security boundary. Unstructured text passing between agents is a prompt injection vector — Agent A's output becomes Agent B's untrusted input."

---

## Build — Multi-Agent Investigation System

Build a multi-agent system with supervisor orchestration for crash investigation.

**Requirements:**
1. **Supervisor agent**: receives crash context, creates investigation plan, delegates to specialists
2. **Log analyst agent**: specializes in OpenSearch queries, has only log-related tools
3. **Metrics analyst agent**: specializes in Prometheus queries, has only metric-related tools
4. **Synthesizer agent**: combines findings from all analysts into a final RCA
5. **Structured handoffs**: JSON-schema validated data passed between agents
6. **Circuit breaker**: if an analyst fails 3 times, skip it and note the gap
7. **Parallel execution**: log and metrics analysts run concurrently
8. **Trace**: full execution trace showing which agent ran when, with what input/output

**Stretch:**
- Add a Verifier agent that checks the final RCA for hallucinated evidence
- Add a Debate mode: two analysts analyze the same data independently, synthesizer resolves disagreements
- Add dynamic routing: supervisor can add analysts based on initial findings (e.g., if logs show network errors, add a Network Analyst)

**What you'll learn:** How agent isolation improves tool selection accuracy, how communication protocol design affects system reliability, why the synthesizer is the hardest agent to get right.

---

## Design — General-Purpose Multi-Agent Orchestration Platform

Design a platform that supports arbitrary multi-agent workflows.

**Requirements:**
- Define workflows as DAGs: nodes are agents, edges are data dependencies
- Support: sequential, parallel, conditional (if/else), and loop patterns
- Per-agent: isolated context, dedicated tools, resource limits (tokens, time, cost)
- Shared state: key-value store with read/write access control per agent
- Monitoring: per-agent metrics (tokens, latency, tool calls), per-workflow metrics (total cost, duration, success rate)
- Fault tolerance: retry failed agents, skip optional agents, human-in-the-loop approval gates

**Design decisions:**
- How do you define workflows? (YAML DSL? Python code? Visual editor?)
- How do you handle agents that need to communicate outside the DAG structure? (e.g., analyst needs to ask supervisor a clarifying question)
- How do you prevent infinite loops in workflows with cycles?
- How do you version and roll back workflows?
- What's the execution runtime? (Async Python? Kubernetes Jobs? Serverless functions?)
