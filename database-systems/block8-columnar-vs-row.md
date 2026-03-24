# Block 8 — Columnar vs Row-Oriented Storage

## The Core Idea

How data is physically laid out on disk determines which queries are fast.

### Row-Oriented (PostgreSQL, MySQL)

Each row is stored contiguously:

```
Disk layout: [id=1, name="Alice", age=30, city="SF"] [id=2, name="Bob", age=25, city="NY"] ...
```

**Fast for:** `SELECT * FROM users WHERE id = 42` (point lookup — read one contiguous block)
**Slow for:** `SELECT avg(age) FROM users` (must read every row, discard name/city columns)

### Column-Oriented (ClickHouse, Parquet, DuckDB)

Each column is stored contiguously:

```
Disk layout:
  id column:   [1, 2, 3, 4, 5, ...]
  name column: ["Alice", "Bob", "Carol", ...]
  age column:  [30, 25, 35, 28, ...]
  city column: ["SF", "NY", "LA", ...]
```

**Fast for:** `SELECT avg(age) FROM users` (read only the age column — skip everything else)
**Slow for:** `SELECT * FROM users WHERE id = 42` (must read from every column file and reassemble)

## Why Columnar Wins for Analytics

### 1. I/O Reduction

Query: `SELECT avg(latency) FROM traces WHERE status = 'error'`

**Row store:** Must read every field of every row, then discard unused columns.
- Reads: `trace_id, timestamp, service, operation, latency, status, tags, ...` for all rows
- If `latency` is 8 bytes out of 200 bytes per row: reading 25x more data than needed

**Column store:** Reads only `latency` and `status` columns.
- Reads exactly the data needed, nothing else
- I/O reduction: 10-50x depending on row width

### 2. Compression

Same-type values stored together compress dramatically better:

```
age column: [30, 30, 31, 30, 31, 32, 30, 31, ...]
  → Run-length encoding: [(30, 4), (31, 2), (32, 1), ...]
  → Or dictionary encoding: {0: 30, 1: 31, 2: 32} + [0, 0, 1, 0, 1, 2, 0, 1, ...]

status column: ["error", "ok", "ok", "error", "ok", ...]
  → Dictionary: {0: "ok", 1: "error"} + bitmap: [1, 0, 0, 1, 0, ...]
```

Typical compression ratios: 5-20x for columnar vs 2-5x for row-oriented.

### 3. Vectorized Execution

Column stores process entire columns at once using SIMD instructions:

```
// Row-oriented: process one row at a time
for row in rows:
    if row.status == "error":
        sum += row.latency

// Column-oriented: process entire column vectors
mask = status_column == "error"    // SIMD comparison, 8 values at once
sum = sum(latency_column[mask])    // SIMD sum of filtered values
```

ClickHouse and DuckDB use this extensively. 10-100x faster than row-at-a-time.

## Real Systems in the Observability Stack

| System | Storage Model | Why | Used For |
|--------|--------------|-----|----------|
| **ClickHouse** | Columnar | Analytics over billions of events | LangFuse traces, Grafana Tempo (optional), Sentry |
| **PostgreSQL** | Row-oriented | ACID transactions, point lookups | LangFuse metadata, Grafana config, app databases |
| **Prometheus TSDB** | Hybrid (column-like) | Time-series optimized: one "column" per series | Metrics storage |
| **Apache Parquet** | Columnar (file format) | Efficient analytics on object storage | InfluxDB IOx, long-term metric archives |
| **Cassandra/ScyllaDB** | Wide-column (row-oriented) | High write throughput, distributed | Cortex chunk storage (legacy) |

### Prometheus TSDB as Hybrid

Prometheus stores each time series as a separate chunk — effectively one "column" per series. Within a chunk, timestamps and values are stored separately (delta-of-delta for timestamps, XOR for values). This is a column-oriented approach optimized for the time-series access pattern: "give me all values for series X between time A and B."

### ClickHouse for Observability Analytics

Why ClickHouse is popular for trace/log analytics:

1. **Columnar**: `SELECT avg(duration) FROM traces WHERE service='api'` only reads `duration` and `service` columns
2. **Compression**: 10-20x compression on structured log data
3. **MergeTree engine**: LSM-like — writes are fast (append), reads are fast (sorted, indexed)
4. **Materialized views**: Pre-aggregate on insert (like Prometheus recording rules but for logs)
5. **SQL interface**: Familiar query language, wide tool support

## The Wide-Column Model (Bigtable / Cassandra)

Not truly columnar in the analytics sense. Each row has a key, and columns are grouped into column families.

```
Row key: "user:42"
  Column family "profile": {name: "Alice", age: 30}
  Column family "activity": {last_login: "2026-03-15", page_views: 1234}
```

- Rows are sorted by key (important for range scans)
- Column families are stored separately on disk
- Sparse: different rows can have different columns
- Optimized for: high write throughput, range scans by key, distributed at scale

**In observability:** Cassandra was used by Cortex for chunk storage. Each chunk stored as a row, key = series_id + time_range.

## Exercises

1. For three systems you use (ClickHouse, PostgreSQL, Prometheus TSDB), classify as row/column/hybrid and explain why that orientation fits their workload.
2. Write a query that's fast on columnar and slow on row-oriented. Then the reverse. Explain why.
3. Explain why LangFuse uses ClickHouse for trace analytics but PostgreSQL for metadata.
4. Calculate: a trace record has 20 fields averaging 50 bytes each (1000 bytes/row). An analytics query touches 3 fields. What's the I/O reduction from columnar storage?

## Key Takeaways

> "Column stores read only the columns a query needs. For analytics queries that touch 3 fields out of 20, that's an instant 6-7x I/O reduction before compression even kicks in. This is why ClickHouse handles billions of traces efficiently."

> "Row stores excel at point lookups and transactions — reading one complete record is a single sequential read. Column stores excel at analytics — scanning one field across millions of records. Choose based on your access pattern, not the hype."

---

## Build — Mini Columnar Store

Implement a simplified columnar storage engine and compare it to row-oriented.

**Requirements:**
1. **Row store**: store records as `[{id, service, method, status, latency, timestamp}, ...]`
2. **Column store**: store each field as a separate array: `ids = [...]`, `services = [...]`, `latencies = [...]`
3. Implement for both stores:
   - `insert(record)` — add a record
   - `scan_column(column_name) -> array` — return all values for one column
   - `filter_scan(column_name, predicate) -> [record_ids]` — return IDs matching condition
   - `aggregate(column_name, fn)` — compute avg/sum/min/max for a column
4. Add **dictionary encoding** for low-cardinality string columns (e.g., status: {0: "200", 1: "404", 2: "500"})
5. Add **run-length encoding** for sorted/repeated integer columns
6. **Benchmark**: insert 1M records. Compare:
   - `SELECT avg(latency) WHERE status = "500"` — column store should win
   - `SELECT * WHERE id = 42` — row store should win

**What you'll learn:** The I/O difference is dramatic even at small scale. Dictionary and RLE encoding compress low-cardinality columns 10-50x.

---

## Design — Trace Analytics Store

Design the storage backend for a trace analytics system (like what LangFuse uses ClickHouse for).

**Requirements:**
- Store trace records: `{trace_id, span_id, parent_span_id, service, operation, duration_ms, status, attributes: {}, timestamp}`
- Support analytics queries: "average duration by service where status = error, last 24 hours"
- Support point lookups: "give me all spans for trace_id = abc123"
- 100M traces/day, 30-day retention

**Design decisions:**
- Columnar (ClickHouse) or hybrid? Why?
- How do you partition data? (By time? By trace_id hash?)
- How do you serve both analytics queries (columnar scan) and trace lookups (point query) efficiently?
- What materialized views / pre-aggregations would you create?
- How do you handle the `attributes` field (variable schema, nested JSON)?
