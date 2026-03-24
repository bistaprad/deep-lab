# Day 5 — Horizontal Scaling: Thanos, Mimir, and the Cardinality Story

## The Core Problem

Single Prometheus instance limits:
- ~1-2M active series before memory pressure gets serious
- ~500k-1M series/sec ingestion before scrape latency degrades
- Single point of failure
- Local storage only: 15-30 days retention typical

At 30M series you hit all of these simultaneously.

## Federation (Naive Scaling)

A "global" Prometheus scrapes aggregated metrics from "leaf" instances via `/federate`.

**Why it falls short:**
- Pull-based, query-time — not replication
- Global instance only has pre-aggregated data
- Cannot query raw series without hitting leaves directly
- Useful for cross-cluster summaries, not real horizontal scale

## Thanos (Self-Managed Production Solution)

### Components

| Component | Role | Stateful? |
|-----------|------|-----------|
| **Sidecar** | Runs next to each Prometheus. Exposes gRPC Store API. Uploads completed blocks to object storage every 2h. | No (proxy) |
| **Query** | Global query layer. Fans out to Sidecars + Store Gateways. Deduplicates HA pairs. | No |
| **Store Gateway** | Serves historical data from object storage. Caches block indexes locally. | Yes (local cache) |
| **Compactor** | Merges and downsamples blocks in object storage. 5m and 1h resolution for old data. | No (batch) |
| **Ruler** | Evaluates recording rules and alerts against Thanos Query. | No |

### Query Flow

```
PromQL request
     ↓
Thanos Query
     ├── Fan out to Sidecars (recent data, last 2h)
     ├── Fan out to Store Gateways (historical data)
     ↓
Merge + deduplicate by external_labels
     ↓
Return unified result
```

### HA Deduplication

Two Prometheus instances scrape the same targets (HA pair).
- Replica 0: `external_labels: {replica: "0"}`
- Replica 1: `external_labels: {replica: "1"}`
- Thanos Query deduplicates by preferring replica="0" for overlapping samples
- Result: zero-gap data even when one Prometheus restarts

## Mimir / Cortex (Distributed, Horizontally Scalable)

Grafana Cloud runs on Mimir. Cortex is the open-source predecessor.

### Components

| Component | Role | Stateful? |
|-----------|------|-----------|
| **Distributor** | Receives remote_write. Hashes series to Ingesters. Replication factor 3. | No |
| **Ingester** | In-memory TSDB (Head block equivalent). WAL on local disk. Flushes to object storage. | Yes |
| **Querier** | Handles PromQL. Fans out to Ingesters + Store Gateways. | No |
| **Store Gateway** | Serves historical blocks from object storage. | Yes (cache) |
| **Compactor** | Merges and downsamples blocks in object storage. | No (batch) |
| **Ruler** | Distributed rule evaluation. | No |

### Write Path

```
remote_write → Distributor → hash(series labels) → consistent hash ring → 3 Ingesters
Each Ingester: WAL append → Head block write → periodic flush to object storage
```

### Read Path

```
PromQL → Querier → fan out to Ingesters (recent) + Store Gateways (historical) → merge
```

### Sharding: The Hash Ring

Series are sharded across Ingesters using consistent hashing.
- Ring uses virtual nodes (tokens) for even distribution
- Hash ring managed via KV store (etcd, Consul, or memberlist)
- Adding/removing Ingesters: tokens redistribute, series migrate

### Why Mimir Over Thanos

| | Thanos | Mimir |
|---|--------|-------|
| **Architecture** | Sidecar per Prometheus | Prometheus remote_writes to Distributors |
| **Write scalability** | Bound by Prometheus instances | Distributors are stateless, scale horizontally |
| **Multi-tenancy** | Manual via separate Prometheus | Built-in via `X-Scope-OrgID` header |
| **Operational complexity** | Lower (Sidecars are simple) | Higher (requires object storage + KV store) |
| **Query performance** | Good, limited by Store Gateway | Better with query sharding |

## VictoriaMetrics (Alternative)

- Single-binary or cluster mode
- More aggressive compression (~3-5x better disk usage than Prometheus TSDB)
- Different storage format: row-oriented, then column-oriented compression
- Faster ingestion at high cardinality
- Drawback: less ecosystem integration than Mimir/Thanos
- Strong choice for cost-sensitive deployments with less Grafana integration needs

## The Cardinality Reduction Approach

30M series → ~1-3M series (90-95% reduction).

### Systematic Process

**Step 1: Profile** — Top 10 metric names by series count.
```promql
topk(10, count by (__name__)({__name__=~".+"}))
```

**Step 2: Identify** — For each high-cardinality metric, which labels have unbounded values?

**Step 3: Reduce** — Options per metric:
- Drop the label entirely (relabel config)
- Replace with bucketed value (e.g., latency ranges instead of exact values)
- Aggregate at scrape time (recording rules)
- Drop the metric if never queried

**Step 4: Recording rules** — Pre-aggregate high-cardinality metrics into lower-cardinality ones.
```yaml
record: job:http_requests_total:rate5m
expr: sum by(job) (rate(http_requests_total[5m]))
```

**Step 5: Drop unused metrics** — Scan Grafana dashboards and alert rules. If a metric isn't referenced anywhere, drop it.

### Tools

- `mimirtool analyze grafana` — scans dashboards, reports which metrics are actually used
- Prometheus `/api/v1/label/__name__/values` — list all metric names
- Prometheus `/api/v1/series?match[]=...` — count series matching a selector

### The Organizational Challenge

Cardinality reduction is a product decision, not just a technical one. Engineers resist removing labels they think they might need. Requires building consensus around what "useful" means — and having dashboards that prove which labels are never queried.

## Exercises

1. Draw the Thanos architecture from memory. Then draw Mimir. Identify where they overlap (Store Gateway, Compactor) and where they diverge (Sidecar vs Distributor/Ingester).
2. A team remote-writes 5M series to Mimir. The hash ring has 10 Ingesters. Roughly how many series per Ingester? What happens when you add 2 more Ingesters?
3. Write a 1-page comparison: Thanos vs Mimir vs VictoriaMetrics. When would you pick each?

## Key Takeaways

> "Thanos extends existing Prometheus instances with a global query layer and object storage. Mimir replaces the storage layer entirely — Prometheus becomes a scraper that remote-writes to a distributed backend."

> "Cardinality reduction at scale is more organizational than technical. The hard part isn't writing relabel configs — it's getting 50 teams to agree which labels they can live without."

---

## Build — Consistent Hash Ring

Implement a consistent hash ring with virtual nodes, similar to Mimir's Distributor.

**Requirements:**
1. `Ring` data structure: sorted list of (token, node_id) pairs
2. `add_node(node_id, num_tokens)` — place N virtual nodes on the ring
3. `remove_node(node_id)` — remove all tokens for a node
4. `get_nodes(key, replication_factor) -> [node_id]` — find N responsible nodes for a given key
5. Hash function: use FNV-1a or xxHash on the key string
6. Simulate: create 5 nodes with 128 tokens each. Distribute 100,000 series keys. Measure distribution evenness (std deviation of series count per node).
7. Remove 1 node. Measure: what % of keys moved? (Should be ~1/N)

**Stretch:** Implement zone-aware replication — replicas must land on different availability zones.

**What you'll learn:** How Mimir distributes series across Ingesters, why virtual nodes matter for even distribution, what happens during node failure and recovery.

---

## Design — Federated Metrics Aggregator

Design a system that queries multiple Prometheus instances and provides a unified global view (like Thanos Query, but your own).

**Requirements:**
- Register multiple Prometheus endpoints
- Accept PromQL queries, fan out to all registered Prometheus instances
- Merge results: handle overlapping time ranges from HA pairs
- Deduplicate: if two Prometheus instances scraped the same target, pick one
- Cache recent query results for repeated dashboard refreshes

**Design decisions:**
- How do you deduplicate HA pairs? (External labels? Timestamp comparison?)
- What consistency do you provide? (Read from all and merge? Quorum?)
- How do you handle a slow Prometheus instance? (Timeout and return partial results? Wait?)
- How do you parallelize fan-out queries? What's the latency model?
