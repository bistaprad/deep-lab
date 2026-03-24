# Day 6 — Why AI Monitoring Is Different + The Four Layers

## The Fundamental Shift

| | Traditional Software | AI Pipelines |
|---|---------------------|--------------|
| **Determinism** | Same input → same output | Same input → different output each time |
| **Correctness** | Binary: succeeded or failed | Spectrum: partially correct, mostly right, subtly wrong |
| **Standard signals** | Latency, error rate, throughput (RED) | Those + output quality, faithfulness, toxicity, drift |
| **Failure modes** | Timeout, OOM, connection refused | Hallucination (no error thrown), prompt injection, reasoning loops, silent degradation |

Traditional APM catches infrastructure failures but misses the most important AI-specific failures entirely. An LLM can return HTTP 200 with a confident, well-formatted, completely fabricated answer.

## The Four Layers of AI Observability

### Layer 1: Infrastructure Metrics (Traditional)

What you already know how to do.

- GPU utilization, GPU memory, token throughput, API latency, error rates
- Tools: Prometheus, Datadog, existing APM
- For API-based agents (Claude API): input/output tokens, latency per call, cost

### Layer 2: LLM Request/Response Tracing

Full capture of the model interaction.

- Prompts, completions, tool calls, token counts, finish reasons
- Conversation history length, model parameters (temperature, max_tokens)
- Tools: LangFuse, LangSmith, Helicone, Arize Phoenix

### Layer 3: Output Quality Evaluation

Automated scoring of outputs against quality criteria.

- LLM-as-judge scoring (accuracy, completeness, hallucination detection)
- Reference-based eval (compare to known-good outputs)
- Tools: LangFuse evals, Braintrust, Humanloop, custom eval harnesses

### Layer 4: Behavioral Monitoring

Pattern detection across millions of interactions.

- Alignment monitoring, misuse detection, emergent behavior surfacing
- Does the system behave consistently across different input distributions?
- Does performance degrade over time, or after model version changes?
- Tools: mostly custom; hierarchical summarization approaches

## Mapping to the Crash Triage Agent

| Layer | What to Monitor | Concrete Example |
|-------|----------------|------------------|
| 1 | API latency, token cost, tool response times | Claude API p99 > 30s → alert |
| 2 | Full investigation trace: prompts, tool calls, completions | Every OpenSearch query + result logged |
| 3 | RCA accuracy scored against ground truth | LLM-as-judge rates each investigation |
| 4 | Does accuracy differ by crash type? Degrade over time? | Weekly accuracy by category trend |

## Key Failure Modes That Only AI Monitoring Catches

1. **Hallucinated evidence:** Agent cites a log line that doesn't exist. HTTP 200, valid JSON, completely wrong. Layer 3 catches this.

2. **Reasoning loop:** Agent calls the same tool 15 times with slightly different parameters, burning tokens and time. Layer 2 (tool_call_count metric) catches this.

3. **Silent model regression:** Claude model version updates, p99 latency unchanged, but RCA accuracy drops 15%. Layer 3 + Layer 4 catch this.

4. **Confidence miscalibration:** Agent says "high confidence" on 95% of investigations regardless of actual accuracy. Layer 4 (confidence vs accuracy correlation) catches this.

## Exercises

1. For your crash triage agent, list one specific metric at each of the four layers. What would you alert on?
2. A traditional APM dashboard shows all green for your agent (low latency, zero errors). What could still be badly wrong?
3. Design a Grafana dashboard for the crash triage agent. What panels would you include? Organize by layer.

## Key Takeaways

> "An LLM can fail with HTTP 200 and valid JSON. The most dangerous AI failures produce no errors, no exceptions, no alerts in traditional monitoring. That's why you need quality evaluation as a first-class observability signal."

> "Layer 2 (tracing) is table stakes. Layer 3 (evals) is where most teams stop. Layer 4 (behavioral monitoring at scale) is the frontier — and the hardest to get right."

---

## Build — LLM Call Wrapper with 4-Layer Telemetry

Build a Python wrapper around the Claude API that captures telemetry at all 4 observability layers.

**Requirements:**
1. Wrap `client.messages.create()` and automatically capture:
   - **Layer 1**: latency, input_tokens, output_tokens, cost (as Prometheus metrics)
   - **Layer 2**: full trace (system prompt hash, user message, completion, tool calls, finish_reason)
   - **Layer 3**: call an LLM-as-judge scorer on the output, store the score
   - **Layer 4**: log the model_version, track confidence distribution
2. Expose a Prometheus `/metrics` endpoint from the wrapper
3. Write traces to a local JSON file (simulating LangFuse)
4. Print a per-call summary: `model=claude-sonnet tokens_in=1234 tokens_out=567 latency=2.3s cost=$0.02 eval_score=4/5`

**What you'll learn:** How little code it takes to instrument an LLM call, what data you actually have vs what you wish you had.

---

## Design — AI Observability Dashboard

Design the Grafana dashboard layout for monitoring an AI agent in production.

**Requirements — panels for each layer:**
- **Layer 1**: API latency p50/p95/p99, error rate, token throughput, cost per hour
- **Layer 2**: traces per minute, avg tool calls per trace, top tools by call count
- **Layer 3**: eval score distribution (histogram), eval score trend (time series), pass rate
- **Layer 4**: score by crash category, confidence vs accuracy scatter, model version changes

**Design decisions:**
- How do you link from a metric alert to the specific traces that triggered it?
- How do you detect model version changes visually?
- What drill-down path does an on-call engineer follow: dashboard → trace → specific tool call?
