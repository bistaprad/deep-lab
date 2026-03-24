# Day 1 — The Prometheus Data Model

## Core Concept

Everything in Prometheus is a **time series**, uniquely identified by metric name + label set.

```
http_requests_total{method="GET", status="200", handler="/api/v1/users"}
```

Internally stored as a **fingerprint** — a `uint64` hash of the sorted label set.

## Metric Types

| Type | Behavior | Use Case | Gotchas |
|------|----------|----------|---------|
| **Counter** | Monotonically increasing, resets to 0 on restart | Request counts, bytes transferred | Must use `rate()` or `increase()` to get useful data |
| **Gauge** | Goes up and down | Memory usage, temperature, queue depth | Can use directly, or with `deriv()` for rate of change |
| **Histogram** | Buckets observations client-side | Latency, request size | Buckets defined at instrumentation time; quantiles computed at query time |
| **Summary** | Computes quantiles client-side | Latency (legacy) | **Cannot aggregate across instances** — this is the critical limitation |

## Histogram vs Summary — The Key Distinction

**Why histograms win at scale:**
- Histogram buckets can be aggregated: `histogram_quantile(0.99, sum(rate(http_request_duration_bucket[5m])) by (le))`
- This works across 1000 pods because you're summing bucket counts.
- Summary quantiles are pre-computed on each instance. You cannot mathematically combine pre-computed quantiles.
- Trade-off: histogram accuracy depends on bucket boundaries. Choose boundaries that match your SLOs.

## Cardinality — The Scaling Constraint

Each unique combination of label values = one time series.

```
{status="200", pod="pod-1"}  → series 1
{status="404", pod="pod-1"}  → series 2
{status="200", pod="pod-2"}  → series 3
{status="404", pod="pod-2"}  → series 4
```

2 status values × 2 pods = 4 series. Now imagine 500 status codes × 10,000 pods.

**Rule of thumb:** No label should have more than ~1,000 unique values in production.

**High cardinality sources:**
- `user_id`, `request_id`, `ip_address` — unbounded, never use as labels
- `pod` — bounded but can be large (10,000+)
- `path` — if parameterized URLs aren't normalized: `/users/123`, `/users/456` = unbounded

At 30M series: memory pressure, slow queries, OOM risk, multi-second query latency.

## Exercises

1. Given a metric `api_latency_bucket{le="0.1"} 500`, `api_latency_bucket{le="0.5"} 900`, `api_latency_bucket{le="1.0"} 950`, `api_latency_bucket{le="+Inf"} 1000`, compute the p99 latency.
2. You have a service with 50 endpoints, 10 HTTP status codes, deployed across 200 pods. How many time series does a single histogram metric with these labels produce? (Remember: histogram creates `_bucket`, `_sum`, `_count`.)
3. A team wants to add `customer_id` as a label on their request counter. There are 500,000 customers. What do you tell them?

## Key Takeaways

> "Cardinality is a product decision, not just a technical one. You need engineers to agree to remove labels they think they might need."

> "Histograms aggregate; summaries don't. At scale, that's the entire difference."

---

## Build — Metrics Library

Implement a small metrics library in any language (Python, Go, Rust, etc.) that supports Counter, Gauge, and Histogram types.

**Requirements:**
1. `Counter`: `inc()`, `inc(n)`. Value never decreases. Expose total.
2. `Gauge`: `set(v)`, `inc()`, `dec()`. Can go up or down.
3. `Histogram`: `observe(value)` with configurable bucket boundaries. Track `_bucket`, `_sum`, `_count`.
4. Each metric has a name and a set of label key-value pairs.
5. `render()` method that outputs Prometheus text exposition format:
   ```
   http_requests_total{method="GET",status="200"} 1234
   http_request_duration_bucket{le="0.1"} 500
   http_request_duration_bucket{le="0.5"} 900
   http_request_duration_bucket{le="+Inf"} 1000
   http_request_duration_sum 456.78
   http_request_duration_count 1000
   ```
6. A `Registry` that holds all metrics and can render the full `/metrics` page.

**Stretch:** Add `histogram_quantile()` — compute an approximate quantile from bucket counts using linear interpolation.

**What you'll learn:** How metric types map to storage (each label combo = one series), why histograms produce multiple series per metric, how the exposition format works.

---

## Design — Cardinality Analysis Service

Design a service that continuously monitors Prometheus for cardinality problems.

**Requirements:**
- Query Prometheus API periodically to get series counts per metric name
- Detect metrics whose series count is growing unexpectedly (e.g., > 10% week-over-week)
- Identify which labels are high-cardinality by querying label values
- Cross-reference with Grafana dashboards (via API) to find metrics that are high-cardinality but never queried
- Produce a report: "These 5 metrics account for 60% of series. Label `pod` on metric X has 12,000 values. Metric Y is never used in any dashboard."

**Sketch the architecture:**
- What APIs do you query? (Prometheus `/api/v1/label/__name__/values`, `/api/v1/series`, Grafana dashboard API)
- Where do you store historical cardinality data for trend detection?
- How do you alert? (Prometheus alert rules? Slack webhook?)
- How do you handle false positives (legitimate cardinality growth during scale-out)?
