# Day 3 — On-Disk Index Deep Dive & Query Execution

## The Index File Internals

Each persistent block has an `index` file. This is the structure that makes label-based queries fast.

### Logical Layout

```
┌──────────────┐
│ Symbol Table  │  All unique label names + values, deduplicated, referenced by offset
├──────────────┤
│ Series        │  For each series: label set (symbol offsets) + chunk file references
├──────────────┤
│ Posting Lists │  For each label=value: sorted list of series IDs
├──────────────┤
│ Label Indices │  label name → list of values; label name → posting list offset
├──────────────┤
│ TOC (Table    │  Offsets to each section above
│  of Contents) │
└──────────────┘
```

### Posting List Intersection — The Core Algorithm

This is the most performance-critical operation in Prometheus.

Given two sorted posting lists:
```
status="200" → [1, 4, 7, 12, 15, 20, 25, 30]
method="GET" → [1, 3, 7, 9, 12, 18, 25, 28]
```

**Merge intersection** (two-pointer technique):
```
i=0, j=0
list_a[0]=1, list_b[0]=1  → MATCH → result=[1], i++, j++
list_a[1]=4, list_b[1]=3  → 3<4  → j++
list_a[1]=4, list_b[2]=7  → 4<7  → i++
list_a[2]=7, list_b[2]=7  → MATCH → result=[1,7], i++, j++
...
```

**Complexity:** O(n + m) where n and m are list lengths. Not O(n×m).

**At 30M series with a broad `job="api-server"` label:** posting list could be 5M entries. Intersection of two 5M lists is measurable — hundreds of milliseconds.

### Delta Encoding of Posting Lists

Raw: `[1, 4, 7, 12, 15, 20]`
Delta: `[1, 3, 3, 5, 3, 5]`

Deltas are small numbers → fewer bits needed → snappy-compressed on top.
Result: posting lists are very compact on disk despite large series counts.

## Query Execution Walkthrough

### Example: `rate(http_requests_total{status="200", method="GET"}[5m])`

**Phase 1: Series Selection** (index lookups)
```
1. Parse label matchers: __name__="http_requests_total", status="200", method="GET"
2. For each matcher, load posting list from index
3. Intersect all posting lists → matching series IDs
4. For each series ID: load chunk references (min_time, max_time, file_offset)
```

**Phase 2: Chunk Reading** (data access)
```
5. Filter chunk references to those overlapping [now-5m, now]
6. For each relevant chunk: seek to file_offset in chunks/ file
7. Decompress chunk (reverse Gorilla XOR)
8. Extract samples within the [now-5m, now] window
```

**Phase 3: PromQL Evaluation** (compute)
```
9. For each series: apply rate() — (last - first) / duration, handle resets
10. Return instant vector of rate values
```

**Where time is spent:**
- High cardinality → Step 3 dominates (large posting list intersection)
- Long time range → Step 6-7 dominates (many chunks to decompress)
- Many matching series → Step 9 dominates (many rate computations)

## Query Performance Optimization

### Why Recording Rules Matter

Without recording rule:
```promql
sum by(job) (rate(http_requests_total[5m]))
```
→ Touches 10,000 series → intersect posting lists → decompress chunks → compute rate → aggregate.

With recording rule (evaluated every 1m):
```yaml
record: job:http_requests_total:rate5m
expr: sum by(job) (rate(http_requests_total[5m]))
```
→ Dashboard queries `job:http_requests_total:rate5m` → touches ~10 series. 1000x less work.

### Index Cache and Chunk Cache (Thanos/Mimir)

In standalone Prometheus: OS page cache via mmap.
In Thanos Store Gateway / Mimir Store Gateway:
- **Index cache**: memcached/Redis cache for posting lists
- **Chunk cache**: cache decompressed chunks
- Dramatically reduces object storage reads

## Practical: Inspecting Block Data

```bash
# Inside Prometheus container
ls /prometheus/
# Look for directories like 01BKGV7JC0RY8A6MACW3/

# Use promtool to inspect
promtool tsdb list /prometheus/
promtool tsdb dump /prometheus/ --min-time=... --max-time=...

# Examine meta.json
cat /prometheus/01BKGV7JC0RY8A6MACW3/meta.json | jq .
# Shows: ulid, minTime, maxTime, stats (numSamples, numSeries, numChunks)
```

## Exercises

1. Trace this query through the engine on paper, step by step:
   `histogram_quantile(0.99, sum(rate(http_request_duration_bucket{job="api"}[5m])) by (le))`
   How many posting list lookups? How many intersections?
   
2. You have a label `environment` with 3 values and `pod` with 5,000 values. A query filters on both. Which posting list is smaller? Which should be iterated first for efficiency?

3. Explain why mmap means Prometheus RSS is misleading. If Prometheus shows 50GB RSS but the machine has 64GB RAM, is there a problem?

## Key Takeaways

> "The inverted index maps each label=value pair to a sorted posting list of series IDs. Query execution intersects posting lists using a merge join — O(n+m), not O(n×m). This is why label cardinality directly impacts query latency: larger posting lists mean slower intersections."

> "Prometheus mmaps its block files, so RSS includes OS page cache. The real working set is much smaller. This confuses operators who see 50GB RSS and think they need more RAM."

---

## Build — Inverted Index with Posting List Intersection

Implement the core of a Prometheus-style inverted index.

**Requirements:**
1. Data structures:
   - `Series`: id (u64), labels (dict of string→string), samples (list of (timestamp, value))
   - `PostingList`: sorted array of series IDs for a given label=value pair
   - `Index`: maps `(label_name, label_value)` → `PostingList`

2. `add_series(labels, series_id)` — register a series in the index
3. `posting_list(label_name, label_value) -> [series_id]` — return matching series
4. `intersect(list_a, list_b) -> [series_id]` — O(n+m) merge of two sorted lists
5. `query(matchers: [(label, value)]) -> [series_id]` — intersect all posting lists

6. Benchmark: create 100,000 series with 5 labels each. Query with 2 label matchers. Measure:
   - Time to build index
   - Time to query (posting list intersection)
   - Memory usage of the index

**Stretch:**
- Add regex matchers: `label_name=~"regex"` → union of all matching posting lists
- Add NOT matchers: `label_name!="value"` → complement
- Delta-encode posting lists for compact serialization

**What you'll learn:** Why intersection of sorted lists is O(n+m), how index size grows with cardinality, why regex matchers are expensive (union of many posting lists).

---

## Design — Metrics Query Engine

Design a query engine that sits on top of your inverted index and compressed chunks.

**Requirements:**
- Parse a simplified query: `metric_name{label1="value1", label2="value2"}[5m]`
- Use the inverted index to find matching series
- For each series, read the relevant chunk data
- Support: `rate()` (first/last sample, counter reset detection) and `sum() by (label)`
- Return results as JSON

**Design decisions:**
- How do you handle queries that span multiple blocks (in-memory Head + on-disk blocks)?
- How do you parallelize: per-series evaluation, or per-block evaluation?
- What's the memory cost of materializing all matching samples before aggregation?
- How would you add a query cache?
