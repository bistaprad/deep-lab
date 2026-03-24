# Block 10 — Time-Series Database Design Patterns

## The TSDB Design Space

Every TSDB makes tradeoffs across:
- **Ingestion rate**: How many samples/sec can it handle?
- **Query latency**: How fast are range scans and aggregations?
- **Compression**: How compact is the storage?
- **Retention**: How long can data be kept, and at what cost?
- **Operational complexity**: How hard is it to run?

## Comparing TSDB Architectures

### Prometheus TSDB

```
Scrape → WAL → Head (memory) → 2h blocks (disk) → compacted blocks → mmap
```

- **Storage model**: LSM-like with time-based compaction
- **Compression**: Gorilla XOR (~1.37 bytes/sample)
- **Ingestion**: Single-node, ~1-2M active series
- **Query**: Fast for recent data (Head block in memory), disk for historical
- **Retention**: Local disk, typically 15-30 days
- **Strength**: Simplicity, tight integration with Prometheus ecosystem
- **Weakness**: Single-node limit, no built-in HA or global query

### VictoriaMetrics

```
Insert → WAL → Partition by (metricID, timestamp) → MergeTree storage
```

- **Storage model**: Custom merge-tree with aggressive compression
- **Compression**: ~0.4-0.8 bytes/sample (2-3x better than Prometheus)
- **Ingestion**: Single-node handles 5-10M series; cluster mode scales linearly
- **Query**: MetricsQL (PromQL-compatible with extensions)
- **Retention**: Configurable, efficient at long retention due to compression
- **Strength**: Compression ratio, ingestion speed, simple operations
- **Weakness**: Smaller ecosystem than Grafana/Mimir, less community adoption

### InfluxDB IOx (Apache Arrow / DataFusion / Parquet)

```
Write → WAL → In-memory buffer → Parquet files on object storage
Query → DataFusion (vectorized SQL engine) → reads Parquet
```

- **Storage model**: Columnar (Apache Parquet on object storage)
- **Compression**: Parquet columnar compression (excellent for typed data)
- **Ingestion**: Schema-on-write with tags and fields
- **Query**: SQL + InfluxQL + Flux
- **Retention**: Object storage (infinite, cheap)
- **Strength**: SQL query support, object storage backend, columnar analytics
- **Weakness**: Higher query latency for recent data vs in-memory stores

### TimescaleDB

```
PostgreSQL → Hypertables (auto-partitioned by time) → Chunks (each is a PG table)
```

- **Storage model**: B-tree (PostgreSQL) with time-based partitioning
- **Compression**: Native PostgreSQL compression + columnar compression (Timescale 2.0+)
- **Ingestion**: Good for moderate cardinality, leverages PostgreSQL's write path
- **Query**: Full SQL (joins, subqueries, window functions — impossible in PromQL)
- **Retention**: PostgreSQL storage, with automatic chunk dropping for retention
- **Strength**: Full SQL, can join metrics with relational data, PostgreSQL ecosystem
- **Weakness**: Write throughput lower than purpose-built TSDBs, PostgreSQL operational overhead

## Comparison Table

| | Prometheus TSDB | VictoriaMetrics | InfluxDB IOx | TimescaleDB |
|---|---|---|---|---|
| **Bytes/sample** | ~1.37 | ~0.4-0.8 | ~0.5-1.0 (Parquet) | ~2-4 (varies) |
| **Max series (single node)** | ~2M | ~10M | ~5M | ~1M |
| **Query language** | PromQL | MetricsQL | SQL + InfluxQL | SQL |
| **Storage backend** | Local disk | Local disk | Object storage | PostgreSQL |
| **Horizontal scaling** | External (Thanos/Mimir) | Cluster mode | Built-in | Multi-node (Timescale Cloud) |
| **Operational complexity** | Low | Low | Medium | Medium-High |
| **Best for** | Standard Prometheus ecosystem | High-cardinality, cost-sensitive | SQL analytics, long retention | Joining metrics with relational data |

## Downsampling

The practice of reducing data resolution for older data to save storage.

### Why Downsampling?

- Raw 15s data: 5,760 samples/day per series
- At 1M series: ~5.76 billion samples/day → ~8 GB/day compressed
- After 90 days: ~720 GB just for one metric resolution

With downsampling:
- 0-7 days: raw 15s resolution
- 7-30 days: 5-minute resolution (48x reduction)
- 30-365 days: 1-hour resolution (240x reduction)

### How Thanos/Mimir Implement It

**Thanos Compactor:**
1. Reads raw blocks from object storage
2. For each series, computes 5m and 1h aggregates: `min`, `max`, `sum`, `count`, `counter`
3. Writes downsampled blocks back to object storage
4. Original raw blocks kept for configured retention period, then deleted

**Why min/max/sum/count, not just avg?**
- `avg` loses information. You can't compute p99 from averages.
- With `min`, `max`, `sum`, `count`: you can reconstruct average, detect spikes (max), and approximate percentiles.
- `counter` is a special aggregate for counter-type metrics (preserves reset handling).

### Retention Strategies

**Time-based:** Delete data older than X days. Simple but inflexible.

**Resolution-based:** Keep different resolutions for different age brackets. More storage-efficient.

**Policy-based:** Different retention per metric. SLO-critical metrics kept longer at full resolution. Debug metrics dropped aggressively.

```yaml
# Mimir limits_config example
limits:
  compactor_blocks_retention_period: 365d
  
# Thanos downsampling
retention:
  raw: 30d
  5m: 180d
  1h: 365d
```

## Designing a TSDB for a Workload

**Scenario:** 10M active series, 15s scrape interval, 90-day retention, sub-second p99 queries.

**Analysis:**
- Ingestion: 10M / 15s = ~667K samples/sec
- Daily storage (raw): 10M × 5,760 × 1.37 bytes ≈ 79 GB/day
- 90 days raw: ~7.1 TB
- With downsampling (raw 14d + 5m to 90d): ~1.5 TB total

**Architecture choice:** Mimir with object storage
- Distributors: 3 replicas (stateless, easy to scale)
- Ingesters: 10 replicas (667K samples/sec ÷ ~100K/ingester with headroom)
- Store Gateways: 3 replicas (historical queries from object storage)
- Object storage: S3/GCS (~$35/TB/month for 1.5 TB ≈ $52/month)
- Query-frontend with caching for sub-second p99

**Why not Prometheus standalone?** 10M series exceeds single-node capacity.
**Why not VictoriaMetrics?** Could work — but Mimir integrates with existing Grafana stack and provides multi-tenancy.

## Exercises

1. Compare storage formats: Prometheus TSDB vs InfluxDB IOx (Parquet) vs TimescaleDB. What are the tradeoffs for a query like `avg(cpu_usage) by (service) over 7 days`?
2. Design a downsampling strategy for a 90-day retention policy. Calculate storage savings vs raw retention.
3. You have 10M series at 15s interval with 90-day retention. Estimate storage requirements for: (a) all raw, (b) raw 14d + 5m 90d, (c) raw 7d + 5m 30d + 1h 90d.
4. When would you choose TimescaleDB over Prometheus+Mimir? Give a concrete scenario.

## Key Takeaways

> "Every TSDB design is a point in the tradeoff space between ingestion speed, query latency, compression, and operational complexity. There's no universally best TSDB — only the best one for your workload."

> "Downsampling is the difference between 7 TB and 1.5 TB for 90-day retention at 10M series. It's not optional at scale — it's a requirement. The key is preserving enough aggregates (min, max, sum, count) to answer the queries you care about."

---

## Build — Downsampling Engine

Implement a downsampler that reads raw time-series data and produces lower-resolution aggregates.

**Requirements:**
1. Input: raw samples `[(timestamp, value)]` at 15s resolution
2. Output: 5-minute aggregates `[(window_start, min, max, sum, count)]`
3. Handle counter metrics: detect resets (value decrease), compute `counter` aggregate (total increase including resets)
4. Handle gauge metrics: compute `min`, `max`, `avg` per window
5. Write both raw and downsampled data to separate files
6. Query interface: given a time range, automatically choose the best resolution:
   - Last 24h → raw (15s)
   - Last 7d → 5m
   - Last 90d → 1h (add 1h aggregation as stretch)
7. **Benchmark**: Generate 90 days of data for 1000 series. Compare storage size: raw vs 5m vs 1h.

**What you'll learn:** Why min/max/sum/count instead of just avg, how counter reset handling works in downsampled data, the storage savings from resolution reduction.

---

## Design — Multi-Resolution TSDB

Design a time-series database that natively supports multiple resolutions with automatic resolution selection.

**Requirements:**
- Ingest raw data at 15s resolution
- Automatically downsample to 5m and 1h in the background
- Query API selects resolution based on requested time range (transparent to user)
- Store raw data on local SSD (fast, expensive), downsampled on object storage (slow, cheap)
- Support per-metric retention policies: SLO metrics keep raw for 30d, debug metrics keep raw for 7d

**Design decisions:**
- When does downsampling run? (On compaction? On a schedule? On write?)
- How do you handle queries that span two resolutions (e.g., last 25 hours — raw for recent, 5m for older)?
- How do you ensure downsampled data is consistent with raw data? (What if raw is still being ingested?)
- How do you expose resolution to the user? (Automatic? Or let them choose?)
