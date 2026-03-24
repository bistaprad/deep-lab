# Block 17 — Continuous Profiling & SLO-Driven Alerting

## Part 1: Continuous Profiling — The Fourth Pillar

### The Three Pillars (Traditional)

1. **Metrics** — numeric measurements over time (Prometheus)
2. **Logs** — discrete events with context (Loki, OpenSearch)
3. **Traces** — request flow across services (Tempo, Jaeger)

### The Fourth Pillar: Profiles

**Continuous profiling** = always-on CPU/memory/goroutine profiling, sampled at low overhead, stored as time-series data.

Not "I'll attach a profiler when there's a problem." Instead: "profiling data is always available, just like metrics."

### What Profiles Tell You That Other Signals Don't

**Metrics:** CPU usage is 95%. (What, but not why.)
**Logs:** Request took 3 seconds. (What, but not why.)
**Traces:** The database call in the payment service took 2.8s. (Where, but not why.)
**Profile:** 60% of CPU time is spent in `json.Marshal` inside `payment.ProcessOrder`. (Why.)

Profiles answer **why** a service is slow or consuming resources.

### Tools

**Pyroscope** (now part of Grafana Labs):
- Continuous profiling agent + storage + query engine
- Supports: Go, Java, Python, Ruby, Node.js, .NET, Rust, eBPF
- Storage: custom TSDB optimized for profile data
- Query: flamegraph UI with time-range selection and diff mode
- Integration: Grafana data source, link from Prometheus alert → flamegraph

**Parca** (open source, Polar Signals):
- Similar to Pyroscope but uses eBPF for zero-instrumentation profiling
- Language-agnostic via eBPF (profiles any process on the node)
- Columnar storage (FrostDB) for efficient profile analytics

### Profile Types

| Profile Type | What It Measures | When to Use |
|-------------|-----------------|-------------|
| **CPU** | Where CPU time is spent | High CPU usage, slow requests |
| **Memory (alloc)** | Where memory allocations happen | Memory leaks, GC pressure |
| **Memory (inuse)** | Current heap usage by code path | OOM investigation |
| **Goroutine** | Active goroutines by stack trace | Goroutine leaks (Go) |
| **Mutex** | Where lock contention occurs | High latency under concurrency |
| **Block** | Where goroutines block waiting | I/O bottlenecks, channel waits |

### Continuous Profiling in Practice

```
Agent (per pod) → samples stack traces at 100 Hz (1% overhead)
     ↓
Pyroscope server → stores profile data as time series
     ↓
Grafana → query flamegraphs for any time range
     ↓
Workflow: Prometheus alert fires → click through to flamegraph at that time → see exact function causing the issue
```

---

## Part 2: SLO-Driven Alerting

### The Problem with Threshold Alerting

Traditional: `alert if CPU > 80% for 5 minutes`

Issues:
- **Too noisy:** CPU at 82% might be fine. The service is still healthy.
- **Too slow:** By the time you page, users have been affected for 5 minutes.
- **Not user-focused:** CPU usage doesn't directly map to user experience.
- **No budget:** Every alert is equally urgent. No way to distinguish "we're slightly degraded" from "we're burning through reliability fast."

### SLOs: What Users Actually Care About

**SLI (Service Level Indicator):** The measurement.
- Example: proportion of HTTP requests completing in < 500ms

**SLO (Service Level Objective):** The target.
- Example: 99.9% of requests complete in < 500ms over a 30-day window

**Error Budget:** How much failure you can tolerate.
- 99.9% SLO over 30 days = 0.1% error budget = ~43 minutes of downtime
- If you've used 20 minutes: 23 minutes remaining. If you've used 40 minutes: almost out.

### Burn-Rate Alerting

Instead of "alert when metric crosses threshold," alert when **error budget is being consumed too fast.**

**Burn rate** = rate of error budget consumption relative to expected.
- Burn rate 1 = consuming budget at exactly the rate that would exhaust it at the end of the window
- Burn rate 10 = consuming budget 10x faster than sustainable → will exhaust budget in 3 days instead of 30
- Burn rate 100 = budget gone in 7.2 hours

**Multi-window approach (Google SRE recommendation):**

| Severity | Burn Rate | Long Window | Short Window | Response |
|----------|-----------|-------------|--------------|----------|
| Page (critical) | 14.4x | 1 hour | 5 minutes | Wake someone up |
| Page (high) | 6x | 6 hours | 30 minutes | Respond within an hour |
| Ticket | 3x | 3 days | 6 hours | Fix this week |
| Ticket | 1x | 30 days | 3 days | Track and plan |

**Why two windows?** Long window catches sustained burns. Short window prevents alerting on already-resolved issues (the burn stopped 2 hours ago but the 6-hour window still shows it).

### PromQL for Burn-Rate Alerts

```promql
# SLI: proportion of successful requests (< 500ms)
# Total requests rate
sum(rate(http_requests_total[5m]))

# Error rate (requests > 500ms or 5xx)
sum(rate(http_requests_total{status=~"5.."}[5m]))
+ sum(rate(http_request_duration_count{le="0.5",status!~"5.."}[5m]))

# Burn rate over 1 hour (for 99.9% SLO)
(
  1 - (
    sum(rate(http_requests_total{status!~"5.."}[1h]))
    / sum(rate(http_requests_total[1h]))
  )
) / (1 - 0.999) > 14.4
```

### Tools

- **Sloth:** Generates Prometheus alerting rules from SLO definitions. YAML in, PrometheusRule out.
- **OpenSLO:** Vendor-neutral SLO specification format.
- **Pyrra:** SLO dashboard and alerting for Prometheus (Kubernetes-native).
- **Nobl9:** SaaS SLO platform (enterprise).

### SLO for the Crash Triage Agent

| SLI | Target | Error Budget (30d) |
|-----|--------|-------------------|
| Investigation completes in < 5 minutes | 95% | 5% = ~36 hours of slow investigations |
| RCA accuracy score ≥ 3/5 | 90% | 10% = ~72 hours of low-quality output |
| Agent available (not erroring) | 99.5% | 0.5% = ~3.6 hours of downtime |

Burn-rate alert: if RCA accuracy drops such that you'd exhaust the 10% error budget in 3 days → page.

## Exercises

1. Explain the difference between "CPU is at 90%" and "we're burning error budget at 10x." Which is more actionable?
2. Design an SLO for your crash triage agent. What's the SLI? What's the target? How do you compute burn rate?
3. A service has a 99.9% availability SLO over 30 days. It's day 10 and you've used 60% of the error budget. What's the burn rate? Should you page?
4. Explain when you'd use a flamegraph from continuous profiling vs a distributed trace. What question does each answer?

## Key Takeaways

> "Continuous profiling answers 'why is this slow?' — the question that metrics, logs, and traces leave unanswered. Linking Prometheus alerts to Pyroscope flamegraphs closes the gap between 'something is wrong' and 'here's the exact function to fix.'"

> "SLO-driven alerting replaces 'is this metric above a threshold?' with 'are we consuming reliability budget faster than sustainable?' It's noisier-proof, user-focused, and gives you a budget to make tradeoff decisions."

---

## Build — SLO Calculator + Burn-Rate Alerter

Build a tool that computes SLO compliance and burn-rate alerts from Prometheus data.

**Part 1 — SLO Calculator:**
1. Define SLO in config: `{sli: "ratio of requests < 500ms", target: 0.999, window: "30d"}`
2. Query Prometheus for the SLI over the window (total requests, good requests)
3. Compute: current compliance (e.g., 99.85%), error budget remaining (e.g., 42%), budget consumed (e.g., 58%)
4. Output: `SLO: 99.9% | Current: 99.85% | Budget remaining: 42% | Status: WARNING`

**Part 2 — Burn-Rate Alerter:**
1. Compute burn rate over multiple windows: 1h, 6h, 3d
2. Apply multi-window alerting: burn rate > 14.4 over 1h AND > 14.4 over 5m → CRITICAL
3. Generate Prometheus alerting rules (YAML) from SLO definition
4. Test with synthetic data: simulate a 30-minute outage and verify the alerter triggers at the right time

**Stretch:** Build a simple web UI showing error budget burn-down over time.

**What you'll learn:** How to translate SLO targets into concrete PromQL, why multi-window burn-rate is better than simple threshold, how error budgets work in practice.

---

## Design — SLO Platform for a Microservice Architecture

Design a platform that manages SLOs across 50+ services.

**Requirements:**
- Teams define SLOs via YAML (like Sloth). Platform generates Prometheus alerting rules.
- Dashboard: fleet-wide SLO compliance view (all services at a glance)
- Per-service SLO page: error budget burn-down, historical compliance, related alerts
- Integration: auto-create PagerDuty incidents for critical burn-rate alerts
- Governance: prevent deployments when error budget is exhausted (CI gate)

**Design decisions:**
- How do you handle SLOs that depend on downstream services? (Service A's SLO is affected by Service B's outage)
- How do you set meaningful SLO targets? (Start from historical data? Top-down from business requirements?)
- How do you handle SLO violations that are caused by planned maintenance?
- How do you make error budgets actionable? (What does "budget exhausted" mean for a team's roadmap?)
