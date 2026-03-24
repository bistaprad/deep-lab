# Block 22 — Context Management & Memory

## The Hard Problem

LLMs have finite context windows. Even at 200K tokens, a long-running agent can exhaust its context in 10-15 iterations if tool results are large. And research shows that reasoning quality degrades well before the window is full — the "Golden Context Window" for optimal reasoning is ~32K tokens, regardless of the model's maximum.

**Context drift** — degraded reasoning from information decay — causes ~65% of enterprise AI failures. Not raw context exhaustion, but the model losing track of earlier findings as the context grows.

This block covers the strategies for managing context effectively.

## Context Growth in Agent Loops

Each iteration of the ReAct loop adds to the message history:

```
Iteration 1: system_prompt (2K) + user_task (1K) + thought (500) + tool_call (200) + tool_result (3K)
Iteration 2: + thought (500) + tool_call (200) + tool_result (5K)
...
Iteration 10: total context = 2K + 1K + 10 × (500 + 200 + 3K avg) = ~40K tokens
```

At 40K tokens, you're past the golden window. The model starts losing track of findings from iteration 1.

## Strategies

### 1. Result Truncation (Simplest)

Limit tool result size before adding to context:

```python
def truncate_result(result, max_tokens=4000):
    text = json.dumps(result)
    if token_count(text) > max_tokens:
        return text[:max_tokens] + "\n... [truncated, showing first 4000 tokens]"
    return text
```

**Pros:** Simple. Prevents context explosion.
**Cons:** May truncate the most important data (errors often at the end of logs).

**Better:** Intelligent truncation — keep first N and last M tokens, or extract key fields (error messages, timestamps, status codes) and discard verbose content.

### 2. Sliding Window

Keep only the last N messages in context, dropping older ones:

```python
def sliding_window(messages, max_messages=20):
    system = messages[0]  # always keep system prompt
    task = messages[1]     # always keep original task
    recent = messages[-max_messages:]
    return [system, task] + recent
```

**Pros:** Simple, bounded context.
**Cons:** Loses early findings. Agent may re-investigate things it already discovered.

### 3. Summarization (The Production Approach)

Periodically summarize the conversation so far, replacing older messages with a compressed summary:

```python
def summarize_context(messages, summary_interval=5):
    if len(messages) < summary_interval * 2:
        return messages
    
    # Keep: system prompt, task, last N messages
    to_summarize = messages[2:-summary_interval]
    recent = messages[-summary_interval:]
    
    summary = llm.call([
        system("Summarize the investigation so far. Include: "
               "findings, evidence, tools used, remaining questions."),
        user(format_messages(to_summarize))
    ])
    
    return [messages[0], messages[1],
            assistant(f"<investigation_summary>\n{summary}\n</investigation_summary>"),
            *recent]
```

**The anchored iterative summarization pattern:** Don't regenerate the full summary from scratch each time. Instead, merge the new summary into the existing persistent summary:

```python
def anchored_summarize(existing_summary, new_messages):
    return llm.call([
        system("Update this investigation summary with new findings. "
               "Preserve all existing facts. Add new evidence. "
               "Mark contradictions explicitly."),
        user(f"Existing summary:\n{existing_summary}\n\n"
             f"New findings:\n{format_messages(new_messages)}")
    ])
```

This preserves earlier findings while incorporating new ones. Studies show this achieves higher accuracy (4.04 vs 3.43-3.74) for preserving technical details compared to full re-summarization.

### 4. Context Folding

For subtasks, branch into a sub-context, solve the subtask, then fold (summarize) the result back:

```python
def context_fold(main_context, subtask, tools):
    # Branch: create a new context for the subtask
    sub_context = [system_prompt, user(subtask)]
    
    # Solve subtask in isolated context
    sub_result = agent_loop(sub_context, tools, max_iterations=5)
    
    # Fold: add summarized result back to main context
    main_context.append(
        assistant(f"<subtask_result task='{subtask}'>\n{sub_result}\n</subtask_result>")
    )
    return main_context
```

This achieves **10x smaller active context** while matching baseline performance. The subtask gets a clean context with full attention, and only the result flows back.

### 5. Retrieval-Augmented Context (RAG for Agents)

Store investigation findings in a vector store or structured store. When the agent needs earlier findings, retrieve them:

```python
class InvestigationMemory:
    def __init__(self):
        self.findings = []  # structured findings
        self.embeddings = []  # for semantic retrieval
    
    def add_finding(self, finding):
        self.findings.append(finding)
        self.embeddings.append(embed(finding.text))
    
    def retrieve(self, query, k=5):
        query_embedding = embed(query)
        # Return k most relevant findings
        return top_k(self.findings, self.embeddings, query_embedding, k)
```

**When to use:** Long-running agents (50+ iterations) where even summarization isn't enough. The agent's "memory" lives outside the context window and is retrieved on demand.

### 6. Hierarchical Memory (Short-Term + Long-Term)

```
┌──────────────────────────────────────────┐
│ Working Memory (context window)           │
│  - System prompt                          │
│  - Current task                           │
│  - Investigation summary (compressed)     │
│  - Last 5 tool results (full)            │
├──────────────────────────────────────────┤
│ Short-Term Memory (session store)         │
│  - All findings from this investigation   │
│  - All tool results (retrievable)         │
│  - Agent's running hypothesis             │
├──────────────────────────────────────────┤
│ Long-Term Memory (persistent store)       │
│  - Reflexions from past investigations    │
│  - Common RCA patterns (knowledge base)   │
│  - User preferences and feedback          │
└──────────────────────────────────────────┘
```

## Token Counting and Budget Management

```python
class ContextBudget:
    def __init__(self, max_tokens=100000, golden_window=32000):
        self.max_tokens = max_tokens
        self.golden_window = golden_window
    
    def current_usage(self, messages):
        return sum(token_count(m) for m in messages)
    
    def utilization(self, messages):
        return self.current_usage(messages) / self.max_tokens
    
    def needs_compression(self, messages):
        return self.current_usage(messages) > self.golden_window
    
    def remaining_budget(self, messages):
        return self.max_tokens - self.current_usage(messages)
```

**Alert threshold:** context_utilization > 0.85 → compress immediately.
**Quality threshold:** context > golden_window → summarize to maintain reasoning quality.

## Exercises

1. Implement result truncation that keeps the first 1K and last 1K tokens, with a summary of what was truncated in between.
2. Build the anchored iterative summarization pattern. Run a 15-iteration agent with and without it. Compare context size and output quality.
3. A crash investigation generates 5 tool results of ~8K tokens each. The context window is 100K. After how many iterations do you need summarization? What if the window is 32K?

## Key Takeaways

> "Context drift — not context exhaustion — is the primary failure mode. The model loses track of earlier findings long before the window fills. Summarization is about maintaining reasoning quality, not just fitting within limits."

> "Context folding (branch into sub-context, solve, fold result back) achieves 10x context reduction while maintaining quality. It's the most effective pattern for multi-step investigations."

---

## Build — Adaptive Context Manager

Build a context management system that keeps an agent's context within the golden window while preserving all findings.

**Requirements:**
1. **Token counter**: count tokens for each message (use tiktoken or estimate 1 token ≈ 4 chars)
2. **Context budget**: configurable max_tokens and golden_window thresholds
3. **Result truncation**: intelligent truncation that preserves first/last/error sections
4. **Anchored summarization**: when context exceeds golden_window, summarize older messages while preserving the latest N
5. **Context folding**: support for branching into sub-contexts for subtasks
6. **Memory store**: persist all findings to a JSON file for retrieval. Retrieve by keyword search.
7. **Metrics**: expose context_utilization, summarization_count, findings_stored, findings_retrieved

**Test:** Run a 20-iteration simulated agent loop where each tool result is 5K tokens. Verify context stays under golden_window. Verify all findings are retrievable from memory.

**What you'll learn:** How fast context grows in practice, the quality tradeoff of summarization (information loss), how retrieval-augmented memory extends agent capability beyond the context window.

---

## Design — Stateful Agent Memory Service

Design a memory service that provides persistent, queryable memory for a fleet of agents.

**Requirements:**
- Agents write findings: `{agent_id, investigation_id, finding_type, content, timestamp}`
- Agents retrieve findings: by investigation (all findings for this case), by similarity (find similar past findings), by type (all OOM findings)
- Cross-investigation memory: "what did we learn from similar crashes in the past?"
- Memory lifecycle: session memory (cleared after investigation), persistent memory (survives forever)
- Access control: agents can only read their own investigation's session memory, but can read shared persistent memory

**Design decisions:**
- Vector store for semantic retrieval, or structured store with keyword search, or both?
- How do you handle stale memory? (Findings from 6 months ago about a service that's been rewritten)
- How do you prevent memory poisoning? (An agent writes incorrect findings that contaminate future investigations)
- What's the storage backend? (PostgreSQL with pgvector? Dedicated vector DB? Simple JSON files?)
