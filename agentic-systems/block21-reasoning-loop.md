# Block 21 — The Reasoning Loop: Building ReAct from Scratch

## The Core Problem

An LLM is a stateless text-to-text function. Give it a prompt, get a completion. But an agent needs to:
- Observe the environment (read logs, query APIs)
- Reason about what it sees
- Decide on an action
- Execute the action
- Observe the result
- Repeat until done

The reasoning loop is what turns an LLM into an agent. Every framework (LangChain, CrewAI, AutoGen) implements some variant of this loop. Understanding it from scratch means you can build, debug, and optimize agents without being locked to any framework.

## Reasoning Patterns

### ReAct (Reasoning + Acting)

The dominant single-agent pattern. Interleaves thinking and acting:

```
Thought: I need to find the crash logs for pod X. Let me query OpenSearch.
Action: query_opensearch({"query": "pod-x crash", "time_range": "last 1h"})
Observation: [3 log entries about OOM kill...]
Thought: The logs show OOM. Let me check memory metrics in Prometheus.
Action: query_prometheus("container_memory_working_set_bytes{pod='pod-x'}[1h]")
Observation: [Memory spiked to 95% of limit at 14:32...]
Thought: OOM confirmed. Root cause is memory pressure. Let me synthesize the RCA.
Action: submit_rca({category: "OOM", evidence: [...], recommendation: "Increase memory limit"})
```

**Why it works:** Every thought produces an action, every action produces an observation that grounds the next thought. This binding to reality prevents hallucination — the agent can't fantasize because observations correct it.

**Key insight:** ReAct reduces logical errors by ~45% compared to chain-of-thought alone because the environment provides feedback at every step.

### Chain-of-Thought (CoT)

Pure reasoning without actions. The LLM reasons step-by-step in one pass:

```
Let me analyze this crash:
1. The logs show OOM kill at 14:32
2. Memory was at 95% of limit
3. Therefore the root cause is memory pressure
4. Recommendation: increase memory limit
```

**Limitation:** No grounding. If the LLM's initial analysis is wrong, there's no corrective feedback. It's reasoning from its training data, not from the actual environment.

### Plan-and-Execute

Two-phase approach: a planner LLM creates a high-level plan, then an executor LLM carries out each step:

```
PLANNER:
1. Query crash logs from OpenSearch
2. Check memory metrics in Prometheus
3. Check for user-initiated restarts
4. Synthesize RCA from findings

EXECUTOR (step 1):
Action: query_opensearch(...)
Result: [logs...]

EXECUTOR (step 2):
Action: query_prometheus(...)
Result: [metrics...]

... and so on
```

**When to use:** Multi-step research tasks where the full plan is knowable upfront. Better for complex investigations where you want the planner to think holistically before the executor starts acting.

**Tradeoff:** Less adaptive than ReAct — if step 2 reveals something unexpected, the plan may need revision. Good implementations include a "replan" step.

### Reflexion

Meta-reasoning: the agent reflects on its own performance after completing a task and generates guidance for future attempts:

```
Task: Investigate crash...
[Agent runs ReAct loop, produces RCA]
[RCA is scored: accuracy 2/5]

Reflection: I missed checking for user-initiated restarts. Next time, always check
a_user field before investigating infrastructure causes. I also hallucinated a log
entry — I should quote exact log lines, not paraphrase.

[Reflection stored in memory for next investigation]
```

## The Anatomy of a Reasoning Loop

Every framework implements this core loop:

```python
def agent_loop(task, tools, max_iterations=10):
    messages = [system_prompt, user_message(task)]
    
    for i in range(max_iterations):
        # REASON: Ask the LLM what to do next
        response = llm.call(messages)
        
        # CHECK: Is the agent done?
        if response.stop_reason == "end_turn":  # no tool call
            return response.text  # final answer
        
        # ACT: Execute the tool call
        tool_name = response.tool_calls[0].name
        tool_args = response.tool_calls[0].arguments
        tool_result = execute_tool(tool_name, tool_args, tools)
        
        # OBSERVE: Feed the result back
        messages.append(assistant_message(response))
        messages.append(tool_result_message(tool_name, tool_result))
    
    return "Max iterations reached"  # agent didn't converge
```

That's it. This is the entire agent loop. Everything else — memory, planning, security, multi-agent — is built on top of this foundation.

### What Makes It Hard

1. **When to stop:** The agent needs to know when it has enough information. Too few iterations → incomplete analysis. Too many → wasted tokens and potential loops.

2. **Tool selection:** The LLM must choose the right tool from available options. Bad tool selection wastes iterations.

3. **Error recovery:** What happens when a tool call fails? The agent needs to try alternatives, not get stuck.

4. **Context growth:** Each iteration adds to the message history. After 10 iterations with large tool results, you can blow the context window.

5. **Convergence:** Some tasks cause the agent to loop — trying the same action with slightly different parameters. Detecting and breaking loops is critical.

## Implementing Tool Use

### Tool Schema

Tools are described to the LLM as structured schemas:

```python
tools = [
    {
        "name": "query_opensearch",
        "description": "Search OpenSearch logs for crash evidence. Returns matching log entries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "index": {"type": "string", "description": "OpenSearch index pattern"},
                "time_range": {"type": "string", "description": "Time range, e.g. 'last 1h'"},
                "max_results": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    }
]
```

**Design principles for tool schemas:**
- Descriptions should explain *when* to use the tool, not just *what* it does
- Input parameters should have defaults for optional fields
- Constrain parameters to prevent misuse (e.g., max_results cap)
- Return structured data, not raw dumps

### Tool Execution Layer

```python
def execute_tool(name, args, tools, context):
    tool = tools[name]
    
    # Validate arguments against schema
    validate(args, tool.input_schema)
    
    # Scope enforcement (security)
    args = enforce_scope(args, context.ticket)
    
    # Execute with timeout
    try:
        result = tool.function(**args, timeout=30)
    except TimeoutError:
        result = {"error": "Tool timed out after 30s"}
    except Exception as e:
        result = {"error": str(e)}
    
    # Truncate large results to prevent context overflow
    result = truncate(result, max_tokens=4000)
    
    # Audit log
    audit_log(name, args, result, context)
    
    return result
```

## Exercises

1. Trace through the ReAct loop for a crash investigation. Write out the full Thought/Action/Observation sequence for an OOM crash (at least 5 iterations).
2. Compare ReAct vs Plan-and-Execute for your crash triage agent. Which is better for which crash types?
3. What happens when the agent enters a loop (calling the same tool repeatedly)? How do you detect and break it?

## Key Takeaways

> "The agent loop is simple: reason → act → observe → repeat. Every agentic framework is an implementation of this loop. Understanding it from scratch means you can debug any framework and build your own when frameworks don't fit."

> "ReAct's power comes from grounding: every thought produces an action that generates a real observation. The environment corrects the agent's reasoning at every step, preventing hallucination cascades."

---

## Build — ReAct Agent from Scratch

Build a complete ReAct agent using only the Claude API — no frameworks.

**Requirements:**
1. **Agent loop**: the core reason → act → observe loop (see anatomy above)
2. **3+ tools**: implement at least 3 tools (e.g., web_search, calculator, file_reader)
3. **Structured tool schemas**: define tools with JSON Schema input_schema
4. **Tool execution**: parse LLM tool calls, execute, return results
5. **Convergence detection**: detect when the agent is looping (same tool + similar args 3+ times) and force it to conclude
6. **Max iterations**: configurable limit with graceful termination
7. **Trace output**: print the full Thought/Action/Observation chain
8. **Error handling**: tool failures should be returned as observations, not crash the agent

**Stretch:**
- Add a "plan" step before the ReAct loop (Plan-and-Execute hybrid)
- Add Reflexion: after the agent finishes, have it reflect on what it could do better. Store the reflection.
- Implement parallel tool calls (when the LLM requests multiple tools at once)

**What you'll learn:** How little code a ReAct agent actually requires (~100 lines), why tool schema design matters so much, how context grows and why truncation is necessary.

---

## Design — General-Purpose Agent Runtime

Design a runtime that can host any agent (crash triage, code review, customer support) with shared infrastructure.

**Requirements:**
- Register agent "templates": system prompt + tool set + reasoning pattern (ReAct, Plan-Execute, etc.)
- Execute agent tasks: receive input, run the reasoning loop, return output
- Shared services: tool execution, context management, audit logging, metrics
- Per-agent configuration: max_iterations, max_tokens, timeout, tools_allowed
- Agent lifecycle: create, run, pause (waiting for human input), resume, terminate

**Design decisions:**
- How do you isolate agents from each other? (Separate processes? Containers? Shared process with context isolation?)
- How do you handle long-running agents that need to wait for external events (e.g., human approval)?
- How do you version agent templates and roll back if a new prompt version degrades quality?
- What's the interface between the runtime and the reasoning loop? (Can you swap ReAct for Plan-Execute without changing the runtime?)
