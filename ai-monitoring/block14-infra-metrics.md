# Day 9 — Infrastructure Metrics for AI Workloads

## GPU Metrics (DCGM)

NVIDIA's Data Center GPU Manager (DCGM) exposes Prometheus metrics via `dcgm-exporter`.

| Metric | What It Measures | Alert Threshold |
|--------|-----------------|-----------------|
| `DCGM_FI_DEV_GPU_UTIL` | GPU compute utilization % | < 30% (underutilized) or 100% sustained |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | Memory bandwidth utilization | > 90% (bandwidth bottleneck) |
| `DCGM_FI_DEV_FB_USED` | Used GPU framebuffer memory | > 90% of total (OOM risk) |
| `DCGM_FI_DEV_FB_FREE` | Free GPU framebuffer memory | < 1GB |
| `DCGM_FI_DEV_POWER_USAGE` | Power draw in watts | Near TDP (thermal throttling risk) |
| `DCGM_FI_DEV_SM_CLOCK` | Streaming multiprocessor clock | Drops = power/thermal throttling |
| `DCGM_FI_PROF_GR_ENGINE_ACTIVE` | Fraction of time GPU is active | Low = waiting on CPU/IO |
| `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` | Tensor core utilization | Low = not doing matrix ops efficiently |

### Diagnostic Patterns

- **GPU util 100% but tensor core util low:** Compute-bound but not on matrix operations (likely data preprocessing or attention computation overhead)
- **GPU memory near limit:** Batch size too large, or KV cache filling up — will OOM
- **Power throttling:** Clock speed drops when power budget exceeded. Sustained heavy load.
- **GPU util low, memory high:** Memory-bandwidth bound (common in autoregressive generation)

## LLM Inference Metrics

### The Two Latencies

**Time to First Token (TTFT):**
- Latency from request arrival to first output token
- Dominated by **prefill time** (processing the entire prompt through the model)
- At 100k token context: TTFT can be multiple seconds
- User experience: how long before they see the response start streaming

**Time Per Output Token (TPOT):**
- Time between consecutive output tokens during generation
- Dominated by **KV cache memory bandwidth** (autoregressive decoding is memory-bound)
- Relatively constant regardless of prompt length
- User experience: how fast the response streams

### Other Inference Metrics

| Metric | Meaning | Why It Matters |
|--------|---------|----------------|
| Token throughput (tokens/sec) | Combined input + output processing rate | Capacity planning |
| Batch size | Requests processed simultaneously | Higher = better GPU util, higher TTFT |
| KV cache utilization | % of allocated KV cache memory used | Full = requests queued/rejected |
| Queue depth | Requests waiting for inference | User-visible latency |
| Request rejection rate | Requests dropped due to overload | Availability signal |

## Agent-Specific Metrics (Your Crash Triage Agent)

These are the metrics that matter for agentic systems but nobody talks about:

| Metric | What It Tracks | Alert Threshold | Why |
|--------|---------------|-----------------|-----|
| `tool_call_count` | Tool invocations per investigation | > 15 | Agent is looping/stuck |
| `tool_failure_rate` | Failed tool calls / total calls | > 10% | Downstream system issue |
| `agent_loop_iterations` | Think-act cycles before conclusion | > 8 | Inefficient reasoning |
| `context_utilization` | tokens_used / context_window_limit | > 0.85 | Truncation risk |
| `investigation_duration` | Wall clock time per investigation | > 300s | Timeout imminent |
| `retry_count` | Tool call retries | > 3 per tool | Infra instability |
| `escalation_rate` | % escalated to advanced tier | > 40% | Over-escalation |
| `token_cost` | Total tokens × price per investigation | > $2 | Cost anomaly |
| `confidence_score` | Agent's self-assessed confidence | Track distribution | Calibration monitoring |

### Prometheus Metrics Implementation

```python
from prometheus_client import Counter, Histogram, Gauge

investigation_duration = Histogram(
    'agent_investigation_duration_seconds',
    'Time to complete investigation',
    buckets=[30, 60, 120, 180, 300, 600]
)
tool_calls = Counter(
    'agent_tool_calls_total',
    'Tool invocations',
    ['tool_name', 'status']  # status: success/failure
)
context_utilization = Gauge(
    'agent_context_utilization_ratio',
    'Fraction of context window used'
)
```

## For API-Based Agents (Not Self-Hosting Inference)

When using Claude API, you don't manage GPU metrics. Focus on:

1. **Per-investigation:** input_tokens, output_tokens, total_latency, tool_call_count
2. **Aggregate:** cost per day, p99 investigation latency, tool failure rate
3. **Quality:** eval scores over time, confidence calibration
4. **Alerts:**
   - Investigation > 2 minutes (stuck in tool loop)
   - Token consumption > 50k per investigation (cost anomaly)
   - Tool failure rate > 10% (infra issue)

## Exercises

1. List 10 metrics for an LLM inference workload. For each: name, what it measures, alert threshold, why it matters.
2. Define 5 agentic-specific metrics for the crash triage agent with Prometheus metric types (Counter, Histogram, Gauge) and label dimensions.
3. Explain: why does TTFT increase with context length but TPOT stays relatively constant?

## Key Takeaways

> "TTFT is dominated by prefill (processing the prompt) — it scales with input length. TPOT is dominated by KV cache bandwidth during autoregressive decoding — it's roughly constant regardless of prompt size."

> "For agents, the most important metrics aren't latency or errors — they're tool_call_count, context_utilization, and investigation_duration. These catch the failure mode where the agent is running but not converging."

---

## Build — Agent Metrics Exporter

Build a Prometheus metrics exporter for an AI agent's behavioral signals.

**Requirements:**
1. Define and expose these Prometheus metrics:
   - `agent_investigation_duration_seconds` (Histogram, buckets: 30s, 60s, 120s, 180s, 300s)
   - `agent_tool_calls_total` (Counter, labels: tool_name, status)
   - `agent_tokens_total` (Counter, labels: direction=input|output)
   - `agent_context_utilization_ratio` (Gauge)
   - `agent_eval_score` (Histogram, buckets: 1, 2, 3, 4, 5)
   - `agent_cost_dollars` (Counter)
2. HTTP server exposing `/metrics` in Prometheus text format
3. Instrument a simulated agent loop that generates realistic metric values
4. Write 3 Prometheus alerting rules:
   - `agent_tool_calls_total` rate > 15/investigation → "agent looping"
   - `agent_context_utilization_ratio` > 0.85 → "context overflow risk"
   - `agent_investigation_duration_seconds` p99 > 300s → "investigation timeout"

**What you'll learn:** How to translate domain-specific signals into Prometheus metric types, how to choose between Counter/Gauge/Histogram, how alerting rules consume metrics.

---

## Design — GPU Inference Monitoring Stack

Design the monitoring stack for a self-hosted LLM inference cluster (vLLM on Kubernetes with GPUs).

**Requirements:**
- Monitor: GPU utilization, memory, TTFT, TPOT, token throughput, KV cache utilization, queue depth
- Per-model dashboards (multiple models served on same cluster)
- Auto-scale based on queue depth + TTFT threshold
- Alert on: GPU OOM risk, TTFT degradation, inference errors

**Design decisions:**
- How do you collect GPU metrics? (DCGM exporter → Prometheus)
- How do you collect inference metrics? (vLLM built-in Prometheus endpoint)
- How do you correlate GPU metrics with application-level metrics (TTFT)?
- What triggers auto-scaling: queue depth, TTFT, or GPU utilization? What are the tradeoffs?
