# Weekend — PromQL Deep Dive

## Two Evaluation Modes

| Mode | Input | Output | Use |
|------|-------|--------|-----|
| **Instant query** | Expression + single timestamp | Instant vector | Dashboard panels at "now" |
| **Range query** | Expression + time range + step | Matrix (series of instant vectors) | Graphing over time |

## Range Vectors vs Instant Vectors

**Instant vector:** `http_requests_total` — one sample per series at query time.

**Range vector:** `http_requests_total[5m]` — all samples in last 5 minutes per series. Used as input to functions like `rate()`, `increase()`, `delta()`.

## rate() Internals

`rate(http_requests_total[5m])`

1. Takes first and last sample in the 5m window
2. Computes: `(last - first) / time_elapsed`
3. **Counter reset detection:** if value decreases between samples, assumes reset occurred, adds previous value to compensate
4. Requires **at least 2 samples** in the window
5. If `scrape_interval=15s` and `window=5m`: ~20 samples. Plenty.
6. If window < 2× scrape_interval: `rate()` returns nothing.

**Extrapolation:** rate() extrapolates to cover the full window even if the first/last samples don't perfectly align with window boundaries.

### rate() vs irate() vs increase()

| Function | Behavior | Use |
|----------|----------|-----|
| `rate()` | Per-second average over window | Smooth graphs, alerting |
| `irate()` | Per-second rate using only last 2 samples | Spiky/volatile graphs |
| `increase()` | Total increase over window = `rate() × window_seconds` | Human-readable totals |

## Staleness Window

When querying an instant vector, Prometheus looks back **5 minutes** for the most recent sample. If none found, series is excluded.

Configurable: `--query.lookback-delta`

## Aggregation Operators

```promql
sum(rate(http_requests_total[5m])) by (job)
avg(rate(http_requests_total[5m])) by (job, status)
max(container_memory_usage_bytes) by (pod)
count(up == 1) by (job)
topk(5, sum(rate(http_requests_total[5m])) by (handler))
```

**`by` vs `without`:**
- `by (job)` — keep only the `job` label, aggregate everything else
- `without (instance)` — keep all labels except `instance`

## histogram_quantile()

```promql
histogram_quantile(0.99, sum(rate(http_request_duration_bucket[5m])) by (le))
```

How it works:
1. `rate()` computes per-second rate of each bucket counter
2. `sum() by (le)` aggregates across instances (this is why histograms > summaries)
3. `histogram_quantile(0.99, ...)` interpolates within the bucket that contains the 99th percentile

The `le` label (less-than-or-equal) is required. It defines bucket boundaries.

**Accuracy depends on bucket boundaries.** If your p99 falls between `le="0.5"` and `le="1.0"`, the result is a linear interpolation — could be off if the real distribution is skewed.

## Subqueries

```promql
rate(http_requests_total[5m])[1h:1m]
```

Evaluates `rate()` at each 1-minute step over the past 1 hour. Creates a range vector from instant query results.

**Expensive:** runs the inner query many times. Use recording rules instead for dashboards.

## Recording Rules

Pre-compute expensive queries and store as new time series.

```yaml
groups:
  - name: http_rules
    interval: 1m
    rules:
      - record: job:http_requests_total:rate5m
        expr: sum by(job) (rate(http_requests_total[5m]))

      - record: job:http_request_duration:p99
        expr: histogram_quantile(0.99, sum(rate(http_request_duration_bucket[5m])) by (job, le))
```

**Why they matter at scale:** Replace a query over 10,000 series with a query over ~10 series. 1000x less work at dashboard render time.

**Naming convention:** `level:metric:operations` — e.g., `job:http_requests_total:rate5m`

## Label Matching Operators

```promql
http_requests_total{status="200"}          # exact match
http_requests_total{status!="200"}         # not equal
http_requests_total{status=~"2.."}         # regex match
http_requests_total{status!~"4.."}         # negative regex
```

## Binary Operations and Vector Matching

```promql
# Element-wise division (requires matching label sets)
rate(http_errors_total[5m]) / rate(http_requests_total[5m])

# One-to-one matching with explicit label subset
rate(http_errors_total[5m]) / on(job, handler) rate(http_requests_total[5m])

# Many-to-one with group_left
rate(http_errors_total[5m]) / on(job) group_left rate(http_requests_total[5m])
```

## 10 Practice Queries

Write these from scratch, then verify:

1. **Error rate by handler:** Percentage of 5xx responses per handler over 5 minutes.
2. **P99 latency by job:** 99th percentile request duration per job.
3. **Memory usage vs limit:** Ratio of memory working set to limit per pod.
4. **Top 5 endpoints by traffic:** Highest request rate endpoints.
5. **CPU throttling:** Pods where CPU throttling exceeds 25%.
6. **Disk usage prediction:** Predict when disk will be full using `predict_linear()`.
7. **Absent metric alert:** Alert if a critical metric stops being reported.
8. **Rate of change:** Rate of memory increase per pod using `deriv()`.
9. **Availability:** Fraction of time a service was up over the last 24h.
10. **Histogram heatmap:** Request duration distribution suitable for Grafana heatmap.

<details>
<summary>Solutions</summary>

```promql
# 1. Error rate by handler
sum(rate(http_requests_total{status=~"5.."}[5m])) by (handler)
/ sum(rate(http_requests_total[5m])) by (handler)

# 2. P99 latency by job
histogram_quantile(0.99, sum(rate(http_request_duration_bucket[5m])) by (job, le))

# 3. Memory usage vs limit
container_memory_working_set_bytes / container_spec_memory_limit_bytes

# 4. Top 5 endpoints by traffic
topk(5, sum(rate(http_requests_total[5m])) by (handler))

# 5. CPU throttling > 25%
rate(container_cpu_cfs_throttled_periods_total[5m])
/ rate(container_cpu_cfs_periods_total[5m]) > 0.25

# 6. Disk usage prediction (full in 4 hours)
predict_linear(node_filesystem_avail_bytes[1h], 4 * 3600) < 0

# 7. Absent metric alert
absent(up{job="critical-service"})

# 8. Rate of memory increase
deriv(container_memory_working_set_bytes[15m])

# 9. Availability over 24h
avg_over_time(up{job="my-service"}[24h])

# 10. Histogram heatmap
sum(rate(http_request_duration_bucket[5m])) by (le)
```
</details>

## Key Takeaways

> "rate() takes the first and last sample in the window, computes the slope, and adjusts for counter resets. It needs at least 2 samples, which is why the window should be at least 2× the scrape interval."

> "Recording rules are the single most impactful optimization at scale. They convert an O(n) query-time computation into an O(1) lookup against a pre-aggregated series."

---

## Build — Mini PromQL Evaluator

Implement a simplified PromQL evaluation engine.

**Requirements:**
1. Data store: in-memory map of `series_id → [(timestamp, value)]`
2. Parser: parse expressions like `metric_name{label="value"}`, `rate(metric[5m])`, `sum by (label) (expr)`
3. Implement these functions:
   - **Instant vector selector**: `metric{label="value"}` → find matching series, return latest sample
   - **Range vector selector**: `metric[5m]` → return all samples in last 5 minutes
   - **rate()**: `(last - first) / duration` with counter reset detection
   - **sum() by (label)**: group matching series by label, sum values
   - **histogram_quantile(q, buckets)**: linear interpolation within the bucket containing quantile q
4. Feed it synthetic data (generate 100 series with labels, insert 1000 samples each)
5. Run queries and verify results

**Stretch:**
- Add `avg()`, `max()`, `min()`, `count()` aggregations
- Add `increase()` (= rate × window)
- Add binary operators: `metric_a / metric_b` with label matching

**What you'll learn:** How PromQL evaluation actually works (select series → read samples → apply function → aggregate), why counter reset detection matters, how histogram_quantile interpolates.

---

## Design — Recording Rule Engine

Design a service that evaluates recording rules against a metrics store and writes back pre-aggregated results.

**Requirements:**
- Accept rule definitions: `{record: "name", expr: "promql expression", interval: "1m"}`
- On each interval: evaluate the expression, write resulting series back to the store
- Handle rule dependencies: rule B depends on series produced by rule A → evaluate A first
- Expose: rule evaluation duration, rule evaluation errors, last successful evaluation timestamp
- Support rule groups with shared evaluation interval

**Design decisions:**
- How do you detect rule dependency cycles?
- What happens if a rule evaluation takes longer than the interval?
- How do you handle rule evaluation during TSDB compaction (when some data may be temporarily unavailable)?
- How would you distribute rule evaluation across multiple instances for scale?
