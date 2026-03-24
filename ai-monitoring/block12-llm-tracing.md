# Day 7 — LLM Tracing: OpenTelemetry + LangFuse

## What to Capture Per LLM Request

### Inputs
- `system_prompt` (hash for privacy, not raw text in production)
- `user_message`
- `conversation_history_length` (number of turns)
- `tools_available` (list of tool names)
- Model parameters: `model`, `temperature`, `max_tokens`, `top_p`

### Outputs
- `completion` text
- `finish_reason`: `"stop"` | `"length"` | `"tool_use"` | `"content_filter"`
- `tool_calls` made (name + arguments)
- `tool_results` received

### Timing
- `time_to_first_token` (TTFT) — perceived latency for streaming responses
- `time_per_output_token` (TPOT) — generation speed
- `total_latency`

### Tokens & Cost
- `input_tokens`, `output_tokens`
- `cache_read_tokens`, `cache_write_tokens` (if prompt caching enabled)
- `cost = input_tokens × price_in + output_tokens × price_out`

### Quality Signals (computed at capture time)
- `response_length`
- `contains_refusal` (boolean)
- `tool_call_count`

## OpenTelemetry Semantic Conventions for GenAI

Standardized attributes (semconv 1.27+):

```
gen_ai.system:                "anthropic" | "openai" | "vertex_ai"
gen_ai.request.model:         "claude-sonnet-4-20250514"
gen_ai.request.max_tokens:    4096
gen_ai.request.temperature:   0.7
gen_ai.response.finish_reasons: ["end_turn"]
gen_ai.usage.input_tokens:    1234
gen_ai.usage.output_tokens:   567
```

### Span Structure

```
Root span: "chat claude-sonnet-4-20250514"
├── Child span: tool_call "query_opensearch"
│   ├── Attribute: tool.name = "query_opensearch"
│   ├── Attribute: tool.arguments = {...}
│   └── Attribute: tool.result_size = 4096
├── Child span: tool_call "query_prometheus"
└── Span events: token_counts, finish_reason
```

This is the emerging standard. LangFuse and LangSmith both export OTEL-compatible traces.

## LangFuse (Open Source, Self-Hostable)

### Core Concepts

**Trace** — one complete agent interaction (e.g., one crash investigation).

**Span** — a unit of work within a trace (e.g., one tool call, one retrieval step).

**Generation** — one LLM call with inputs, outputs, token counts, latency.

**Score** — quality rating attached to a trace:
- Human labels: thumbs up/down, star rating
- Automated evals: LLM-as-judge scores
- Custom metrics: confidence_score, RCA accuracy

**Dataset** — stored (input, expected_output) pairs for systematic evaluation.

### Architecture

```
Your Agent → LangFuse SDK (async, non-blocking)
                 ↓
          LangFuse Server
                 ↓
          ClickHouse (columnar storage for analytics)
                 ↓
          Dashboard: traces, scores, cost, latency over time
```

Key detail: traces are sent asynchronously via an in-memory queue. The SDK never blocks your agent's hot path.

### Mapping to Crash Triage Agent

```
One investigation = one Trace
├── Generation: initial analysis prompt → Claude response
├── Span: query_opensearch(crash logs)
├── Span: query_prometheus(memory metrics)
├── Generation: follow-up analysis → Claude response
├── Span: query_k8s_events(pod events)
├── Generation: final RCA synthesis → Claude response
└── Scores:
    ├── accuracy: 4/5
    ├── completeness: 5/5
    └── hallucination_detected: false
```

### Prompt Management

LangFuse can version-control your system prompts:
- Deploy new system prompt to 10% of traffic
- Compare scores between prompt versions
- Roll back if quality drops

## LangSmith vs LangFuse Decision

| | LangFuse | LangSmith |
|---|----------|-----------|
| **Hosting** | Self-hosted or cloud | SaaS only |
| **Framework** | Any (Claude SDK, LangChain, custom) | Best with LangChain |
| **Data residency** | Your cluster | LangChain's servers |
| **Auto-instrumentation** | Explicit SDK calls | Automatic if using LangChain |
| **Cost** | Free (self-hosted) | Per-trace pricing |

For sensitive operational data: LangFuse self-hosted. Data never leaves your cluster.

## Exercises

1. Set up LangFuse locally: `docker compose up` from the LangFuse repo. Make a Claude API call instrumented with the LangFuse Python SDK. View the trace.
2. Add tool call child spans to your trace. Verify the full call tree renders in the UI.
3. Write out the OTEL GenAI attributes you'd capture for your crash triage agent. Which are most useful for debugging quality issues?

## Key Takeaways

> "Every LLM call should produce a trace with: model, tokens, latency, finish_reason, and the full input/output. Without this, debugging quality issues in production is impossible."

> "LangFuse's async SDK means tracing adds negligible overhead. The ClickHouse backend handles analytics over millions of traces efficiently."

---

## Build — OTEL-Compatible LLM Tracer

Build a tracing library that captures LLM interactions with OpenTelemetry-compatible spans.

**Requirements:**
1. `Tracer` class that creates a root span for each agent interaction
2. `with tracer.llm_call(model, system_prompt_hash, user_message):` context manager that:
   - Creates a child span with `gen_ai.*` attributes (model, temperature, max_tokens)
   - On exit: records output_tokens, input_tokens, finish_reason, latency
3. `with tracer.tool_call(tool_name, arguments):` context manager for tool invocations
4. Export traces as JSON (OTEL-compatible format): spans with trace_id, span_id, parent_span_id, attributes
5. Test: run a 3-step agent flow (LLM call → tool call → LLM call). Export trace. Verify the parent-child relationships.

**Stretch:** Send traces to a real OTEL Collector or LangFuse instance.

**What you'll learn:** How trace/span hierarchy works, what the OTEL GenAI semantic conventions look like in practice, how async trace export avoids blocking the hot path.

---

## Design — Distributed Tracing Backend for LLM Workloads

Design the storage and query backend for an LLM trace analytics system.

**Requirements:**
- Ingest 10,000 traces/hour, each with 5-20 spans
- Store: trace_id, spans (with LLM-specific attributes), scores, cost
- Support: trace lookup by ID, analytics ("avg latency by model over last 7 days"), score trend queries
- 90-day retention

**Design decisions:**
- ClickHouse (columnar) for analytics + PostgreSQL for metadata? Or single store?
- How do you handle the variable-width `attributes` field in a columnar store?
- How do you link traces to eval scores efficiently?
- How do you implement "find traces where tool X failed" without scanning all traces?
