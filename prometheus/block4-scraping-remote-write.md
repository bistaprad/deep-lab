# Day 4 — Scraping, Remote Write, Staleness

## The Pull Model

Prometheus **pulls** metrics. This is the fundamental design choice.

Every `scrape_interval` (default 15s), Prometheus HTTP GETs each target's `/metrics` endpoint.

**Why pull over push?**
- Prometheus controls the cadence — no thundering herd from targets
- Failed scrape = Prometheus knows immediately (target is down)
- No client-side buffering/queuing complexity
- Simpler target implementation: just serve an HTTP endpoint

**Trade-off:** pull doesn't work well for short-lived jobs (batch jobs, lambdas). Solution: Pushgateway.

## Service Discovery

Targets discovered via:

| Discovery | Mechanism | Common Use |
|-----------|-----------|------------|
| `static_configs` | Hard-coded IP:port | Dev, small clusters |
| `kubernetes_sd_configs` | K8s API watch | Production K8s |
| `consul_sd_configs` | Consul catalog | HashiCorp stack |
| `ec2_sd_configs` | AWS EC2 API | EC2 instances |
| `file_sd_configs` | JSON/YAML files | Bridge to custom systems |

### Kubernetes Service Discovery in Practice

Prometheus watches K8s API for pods/services/endpoints.

**Annotations approach** (simple, common):
```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

**Prometheus Operator approach** (production):
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-server
spec:
  selector:
    matchLabels:
      app: api-server
  endpoints:
    - port: metrics
      interval: 15s
```

ServiceMonitor/PodMonitor CRDs are abstractions — the Operator generates Prometheus scrape configs from them.

## Staleness

When a target disappears (pod killed, scaled down):
1. Prometheus detects failed scrape
2. Writes a **stale marker** sample for all series from that target
3. Stale markers tell the query engine: "series ended here, not a gap"
4. Prevents misleading interpolation across pod restarts
5. Markers expire after 5 minutes if target doesn't reappear

**Why this matters:** Without staleness, if pod-A dies and pod-B starts, queries could interpolate between pod-A's last value and pod-B's first value — completely wrong.

## Remote Write

Prometheus can forward samples to remote storage backends asynchronously.

```yaml
remote_write:
  - url: "https://mimir.example.com/api/v1/push"
    queue_config:
      capacity: 10000
      max_shards: 200
      max_samples_per_send: 2000
      batch_send_deadline: 5s
    write_relabel_configs:
      - source_labels: [__name__]
        regex: "debug_.*"
        action: drop
```

### Queue Mechanics (Know This Cold)

```
Scrape → Head Block → Remote Write Queue → HTTP POST → Remote Backend
                           ↓
                    In-memory buffer
                    Sharded by series
                    Each shard = independent sender
```

**Key parameters:**
- `capacity`: total samples buffered across all shards
- `max_shards`: max parallel senders (each shard sends independently)
- `max_samples_per_send`: batch size per HTTP request
- `batch_send_deadline`: max time before sending a partial batch

**Failure mode:**
1. Remote endpoint slows down (network, backend overload)
2. Shards block waiting for HTTP response
3. Queue fills up (capacity reached)
4. **Samples are dropped** — data loss
5. You see: `prometheus_remote_storage_dropped_samples_total` increasing

**Critical metric to monitor:**
```promql
prometheus_remote_storage_queue_highest_sent_timestamp_seconds
```
If this falls behind `time()`, remote write is lagging. If lag exceeds retention, you lose data.

### Remote Write Protocol

- **Format:** Protobuf (snappy-compressed)
- **Endpoint:** standard `/api/v1/push` (Prometheus remote write spec)
- **Authentication:** Bearer token, basic auth, or mTLS depending on backend
- **Retry:** built-in retry with exponential backoff on 5xx/connection errors

### Write Relabel Configs

Filter what gets remote-written:
```yaml
write_relabel_configs:
  - source_labels: [__name__]
    regex: "go_.*"
    action: drop    # Don't send Go runtime metrics to remote
```

This is how you reduce remote write volume without affecting local queries.

## Exemplars

OpenTelemetry-inspired feature (Prometheus 2.26+).

Attach trace IDs to histogram observations:
```
http_request_duration_bucket{le="0.5"} 1000 # {trace_id="abc123"} 0.45 1609459200
```

**Use case:** Click on a latency spike in Grafana → jump to the exact trace that caused it.

**Storage:** In-memory only (Head block), not persisted to disk blocks. Limited to ~100,000 exemplars.

**Limitations:** Only works with histograms. Requires OTEL-instrumented applications. Grafana needs Tempo/Jaeger integration to resolve trace IDs.

## Exercises

1. Your remote write endpoint goes down for 30 minutes. With default queue settings and 15s scrape interval at 500k series, estimate how quickly the queue fills. What happens to the samples?

2. A pod restarts. Draw the timeline of what Prometheus does: stale marker for old pod, service discovery detects new pod, first scrape of new pod. How long is the gap?

3. You need to remote-write only SLO-relevant metrics (5% of total). Write the `write_relabel_configs`.

## Key Takeaways

> "Remote write is async with an in-memory queue. If the backend is slow, the queue fills and samples are dropped. In production, `prometheus_remote_storage_queue_highest_sent_timestamp_seconds` is the single most important metric to watch."

> "Staleness markers prevent interpolation across pod restarts. Without them, Prometheus would draw a line between the last sample of a dead pod and the first sample of its replacement — completely wrong data."

---

## Build — Scraper + Remote Write Client

Build a minimal Prometheus-compatible scraper and remote write sender.

**Part 1 — Scraper:**
1. HTTP GET a `/metrics` endpoint at configurable interval
2. Parse the Prometheus text exposition format (line by line: metric name, labels, value)
3. Store parsed samples in an in-memory buffer
4. Handle: `# HELP`, `# TYPE`, metric lines, empty lines
5. Detect target failure (HTTP error / timeout) and log it

**Part 2 — Remote Write Client:**
1. Take buffered samples and batch them into a protobuf `WriteRequest` (use the Prometheus remote write proto definition or a simplified JSON version)
2. Send via HTTP POST with snappy compression (or gzip as simplification)
3. Implement a queue with configurable capacity and batch size
4. On send failure: retry with exponential backoff
5. On queue full: drop oldest samples, increment a `dropped_samples` counter
6. Expose `queue_size`, `sent_samples`, `dropped_samples`, `last_send_timestamp` as metrics

**What you'll learn:** The pull model mechanics, text format parsing, queue backpressure dynamics, why sample drops happen under load.

---

## Design — Multi-Tenant Remote Write Gateway

Design a gateway that receives remote write from multiple teams' Prometheus instances and routes to the correct backend.

**Requirements:**
- Accept Prometheus remote write protocol
- Identify tenant from HTTP header (`X-Scope-OrgID`) or source IP
- Per-tenant rate limiting (samples/sec)
- Per-tenant cardinality limiting (max active series)
- Route to different backends per tenant (team A → Mimir cluster 1, team B → Mimir cluster 2)
- Expose: per-tenant ingestion rate, rejection rate, queue depth

**Design decisions:**
- How do you track active series per tenant efficiently? (Bloom filter? HyperLogLog? Exact set?)
- What happens when a tenant exceeds their cardinality limit? Drop new series? Drop samples for existing high-cardinality metrics?
- How do you handle gateway failures? (Stateless with WAL? Or accept some data loss?)
