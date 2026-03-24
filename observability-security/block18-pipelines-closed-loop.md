# Block 18 — Observability Pipelines & the Closed-Loop Vision

## Part 1: Observability Pipelines

### The Problem

At scale, telemetry data flows from thousands of sources to multiple backends. Without a pipeline layer:
- Every app needs to know every backend's endpoint and format
- Changing backends means reconfiguring every app
- No central place to filter, transform, sample, or route data
- Cost control is impossible — everything goes everywhere

### The Pipeline Layer

```
Sources                    Pipeline                     Backends
────────                   ────────                     ────────
Prometheus scrape  ──┐                            ┌──→ Mimir (metrics)
App OTEL SDK       ──┤     ┌──────────────┐       ├──→ Loki (logs)
Kubernetes events  ──┤────→│ OTEL Collector│──────→├──→ Tempo (traces)
eBPF agents        ──┤     │ / Alloy      │       ├──→ Pyroscope (profiles)
Syslog             ──┘     └──────────────┘       └──→ S3 (archive)
                          filter, transform,
                          sample, route, enrich
```

### OpenTelemetry Collector

The emerging standard. Three pipeline types: metrics, logs, traces.

```yaml
receivers:          # How data comes in
  otlp:             # OTEL protocol (gRPC + HTTP)
  prometheus:       # Scrape Prometheus targets
  filelog:          # Tail log files

processors:         # Transform data in flight
  batch:            # Batch for efficient export
  filter:           # Drop unwanted telemetry
  transform:        # Modify attributes, rename metrics
  tail_sampling:    # Sample traces intelligently (keep errors, slow requests)
  memory_limiter:   # Prevent OOM

exporters:          # Where data goes
  otlp:             # Forward to another collector or backend
  prometheus:       # Remote write to Prometheus/Mimir
  loki:             # Send logs to Loki
```

**Deployment patterns:**
- **Agent mode**: DaemonSet on each node. Collects local telemetry, forwards to gateway.
- **Gateway mode**: Central deployment. Receives from agents, processes, routes to backends.
- **Sidecar mode**: Per-pod. Used when per-app processing is needed.

### Grafana Alloy

Grafana's distribution of the OTEL Collector + Prometheus Agent + Loki Agent + Pyroscope Agent. Single binary that replaces multiple agents.

- Configuration language: River (Alloy's HCL-like config)
- Supports all OTEL Collector components plus Grafana-specific ones
- Native Kubernetes service discovery
- Your existing infrastructure already uses Alloy — this connects to your operational experience

### Cost Reduction Strategies

This is where pipelines pay for themselves:

| Strategy | How | Impact |
|----------|-----|--------|
| **Metric filtering** | Drop metrics never queried by any dashboard/alert | 30-60% reduction typical |
| **Label dropping** | Remove high-cardinality labels at pipeline layer | Massive series reduction |
| **Log sampling** | Keep 100% of errors, 10% of info, 1% of debug | 80-90% log volume reduction |
| **Trace tail sampling** | Keep 100% of errors/slow traces, 5% of successful | 90%+ trace volume reduction |
| **Aggregation** | Pre-aggregate metrics in pipeline before storage | Reduces backend load |
| **Deduplication** | Remove duplicate data from HA pairs | 50% for HA setups |

### Tail Sampling (Critical for Traces)

Head sampling: decide at the start of a request whether to sample. Problem: you don't know if the request will be interesting.

Tail sampling: decide at the end. Keep traces that are:
- Errors (status code >= 400)
- Slow (duration > p99)
- From specific services or operations
- Matching specific attributes

```yaml
processors:
  tail_sampling:
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow-requests
        type: latency
        latency: {threshold_ms: 1000}
      - name: baseline
        type: probabilistic
        probabilistic: {sampling_percentage: 5}
```

---

## Part 2: The Closed-Loop Vision

### What Is Closed-Loop Observability?

Traditional observability: **Collect → Visualize → Alert → Human investigates → Human remediates**

Closed-loop observability: **Collect → Analyze → Act → Verify → Learn**

```
┌─────────────────────────────────────────────┐
│                                             │
│   ┌──────────┐    ┌──────────┐    ┌─────┐  │
│   │ Collect  │───→│ Analyze  │───→│ Act │  │
│   │ telemetry│    │ (auto)   │    │     │  │
│   └──────────┘    └──────────┘    └──┬──┘  │
│        ↑                             │     │
│        │          ┌──────────┐       │     │
│        └──────────│ Verify   │←──────┘     │
│                   │ & Learn  │             │
│                   └──────────┘             │
└─────────────────────────────────────────────┘
```

The key difference: **the loop closes automatically**. Observability data drives actions, and the results of those actions are observed to validate and improve.

### Concrete Implementations

**1. Canary Deployments with Observability Gates**

```
Deploy canary (5% traffic)
     ↓
Observe: error rate, latency, CPU, memory (Prometheus)
     ↓
Analyze: compare canary metrics to baseline (automated)
     ↓
Act: if metrics are good → promote to 100%
     if metrics degrade → rollback automatically
     ↓
Verify: confirm rollback restored baseline metrics
```

Tools: Argo Rollouts + Prometheus + Grafana. The "analysis template" queries Prometheus and auto-promotes or rolls back.

**2. Auto-Scaling Based on Custom Metrics**

```
Observe: queue depth, request latency, token throughput
     ↓
Analyze: KEDA (Kubernetes Event-Driven Autoscaling) evaluates Prometheus query
     ↓
Act: scale up/down pods based on metric threshold
     ↓
Verify: observe that latency/queue depth returned to normal after scaling
```

**3. Your Crash Triage Agent IS a Closed Loop**

```
Observe: crash event detected (OpenSearch, Prometheus, K8s events)
     ↓
Analyze: agent investigates root cause (queries tools, reasons)
     ↓
Act: agent produces RCA report, posts to Jira
     ↓
Verify: eval harness scores RCA quality, human reviews
     ↓
Learn: low scores → update KB, refine prompts, add test cases
```

This is the vision: observability as an active participant in operations, not a passive dashboard.

**4. Anomaly Detection → Auto-Remediation**

```
Observe: Prometheus metrics stream
     ↓
Analyze: ML model detects anomalous memory growth pattern
     ↓
Act: trigger pod restart before OOM kill (graceful)
     ↓
Verify: confirm memory usage returned to normal post-restart
     ↓
Learn: log the pattern for future detection improvement
```

Tools: Shoreline.io, Rundeck, PagerDuty Process Automation.

### Observability-Driven Development

The feedback loop extends into the development cycle:

```
Write code → Deploy → Observe in production
     ↑                        │
     │    ┌───────────────────┘
     │    ↓
     │  Profile identifies hot function (Pyroscope)
     │  Trace shows slow DB query (Tempo)
     │  Log shows retry storm (Loki)
     │    │
     └────┘
   Fix and redeploy
```

Not new conceptually, but the tooling to make this tight loop practical is recent:
- Grafana linking: click from Prometheus alert → Tempo trace → Pyroscope flamegraph
- Source code integration: link flamegraph to exact line in repo
- CI integration: run load test → capture profile → compare to baseline → fail if regression

## Exercises

1. Draw the observability pipeline for your infrastructure: sources → collection → processing → backends. Label where cost reduction happens.
2. Design a tail sampling strategy for your crash triage agent's traces: what do you always keep? What do you sample?
3. Map your crash triage agent onto the closed-loop model: Collect → Analyze → Act → Verify → Learn. What's the weakest link?
4. Design a canary deployment with Prometheus-based observability gates. What metrics would you check? What thresholds trigger rollback?

## Key Takeaways

> "Observability pipelines are the control plane for telemetry data. Without them, you're either paying too much (everything stored everywhere) or flying blind (filtering too aggressively). The pipeline is where cost meets signal quality."

> "The closed loop is the future of observability: telemetry → automated analysis → action → verification. Your crash triage agent is already a concrete implementation of this pattern. The difference between a dashboard and a closed loop is agency — the system acts on what it observes."

---

## Build — Mini Telemetry Pipeline

Build a simplified OTEL Collector that receives, processes, and exports telemetry data.

**Requirements:**
1. **Receiver**: HTTP endpoint that accepts JSON telemetry: `{type: "metric"|"log"|"trace", data: {...}}`
2. **Processor chain** (configurable, applied in order):
   - `filter`: drop telemetry matching a predicate (e.g., drop debug logs)
   - `transform`: add/remove/rename attributes
   - `sample`: probabilistic sampling (keep N% of traces)
   - `batch`: buffer records, flush every N seconds or M records
3. **Exporter**: write processed data to file (simulating a backend). Support multiple exporters (one for metrics, one for traces).
4. **Routing**: based on telemetry type, route to different exporter
5. **Metrics about the pipeline itself**: records_received, records_dropped, records_exported, queue_depth

**Stretch:** Add tail sampling: buffer traces for 30s, then decide to keep/drop based on whether any span has an error.

**What you'll learn:** The receiver → processor → exporter model, how filtering reduces cost, how batching improves throughput, how tail sampling requires buffering complete traces.

---

## Design — Closed-Loop Canary Deployment System

Design a system that deploys canaries and automatically promotes or rolls back based on observability signals.

**Requirements:**
- Deploy a new version to 5% of traffic (canary)
- Monitor canary vs baseline: error rate, latency p99, custom business metrics
- Analysis engine compares canary metrics to baseline using statistical tests (Mann-Whitney U or similar)
- If canary is healthy after N minutes → auto-promote to 100%
- If canary degrades → auto-rollback, create incident ticket

**Design decisions:**
- What metrics do you compare? (Just error rate? Latency distribution? Business KPIs?)
- How long do you observe before deciding? (Fixed time? Or adaptive based on traffic volume?)
- What statistical test do you use? (Simple threshold? Mann-Whitney? Bayesian?)
- How do you handle slow-burn regressions that only show up at 100% traffic?
- How does this connect to your SLO framework? (If canary would burn error budget too fast → rollback)
