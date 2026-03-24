# Day 2 — TSDB Storage Engine Internals

## Architecture Overview

```
Scrape → WAL (disk, append-only) → Head Block (memory) → Compaction → Persistent Blocks (disk, immutable)
                                                                            ↓
                                                                     mmap'd into memory
```

## The Head Block (Memory Layer)

New data lands here first. Lives entirely in memory, backed by WAL for durability.

**Default retention in Head:** 2 hours before compaction to disk.

**Inside the Head block:**
- **Chunks**: compressed `(timestamp, value)` pairs for one time series
- **Inverted index**: `label=value → set of series fingerprints`
- **Series map**: `fingerprint → series metadata + chunk reference`
- **WAL**: sequential append-only log for crash recovery

### Gorilla XOR Compression (Critical to Know)

From Facebook's Gorilla paper (2015). Two techniques:

**Timestamps — delta-of-delta encoding:**
```
Raw:      1609459200, 1609459215, 1609459230, 1609459245
Deltas:   15, 15, 15
Delta-of-delta: 0, 0, 0
```
Most timestamps are regular intervals → delta-of-delta is often 0 → 1 bit per timestamp.

**Values — XOR encoding:**
```
Adjacent float64 values often share leading and trailing bits.
XOR of two similar floats has many leading and trailing zeros.
Store: number of leading zeros, number of meaningful bits, the meaningful bits.
```

**Result:** ~1.37 bytes per sample (vs 16 bytes uncompressed = 8-byte timestamp + 8-byte float64). ~12x compression.

## Write-Ahead Log (WAL)

**Purpose:** Crash recovery. Not long-term storage.

**Mechanics:**
1. Every sample is appended to WAL *before* writing to Head block memory
2. WAL segments are 128 MB by default
3. On crash: Prometheus replays WAL to reconstruct Head block
4. WAL is truncated after Head block data is compacted to disk

**WAL record types:**
- **Series records**: new series labels (fingerprint → labels mapping)
- **Sample records**: `(fingerprint, timestamp, value)` tuples
- **Tombstone records**: marks for deleted series

## Compaction — Head to Persistent Blocks

Every ~2 hours, the Head block is flushed to disk as an immutable **Block**.

**Block directory structure:**
```
01BKGV7JC0RY8A6MACW3/
├── chunks/        # Compressed time series data (multiple chunk files)
│   └── 000001
├── index          # Inverted index + series metadata
├── meta.json      # Block metadata: ULID, time range, stats
└── tombstones     # Deletion markers
```

**Leveled compaction** (similar to LSM trees):
```
2h blocks → compacted to 4-6h → compacted to 12-24h → multi-day blocks
```

Benefits: fewer files to scan at query time, better compression ratios.

## The On-Disk Index (Inside Each Block)

This is the key to fast queries. Structure:

### Symbol Table
- All label names and values stored once, deduplicated
- Referenced by integer offset
- Why: compact storage even with high cardinality on disk

### Posting Lists
- For each `label=value` pair: sorted list of series IDs
- Example: `status="200"` → `[1, 4, 7, 12, ...]`
- Stored as delta-encoded uint32 lists, snappy-compressed

### Series Records
- For each series ID: label set (as symbol offsets) + chunk references
- Chunk reference = `(min_time, max_time, file_offset)` tuple

### Label Name Index & Label Value Index
- Enable fast enumeration (Grafana autocomplete)

## How a Query Executes

Query: `http_requests_total{status="200", method="GET"}`

```
Step 1: Posting list for status="200"  → [1, 4, 7, 12, 15, ...]
Step 2: Posting list for method="GET"  → [1, 3, 7, 9, 12, ...]
Step 3: Intersect sorted lists         → [1, 7, 12, ...]        O(n) merge
Step 4: For each match: look up chunk references
Step 5: Seek to file offsets, decompress chunks
Step 6: Filter to requested time range
Step 7: Return to query engine
```

**Why cardinality matters here:** Larger posting lists → slower intersection at Step 3.

## mmap

Prometheus mmaps index and chunk files into virtual memory. The OS page cache manages physical memory.

**Implications:**
- Prometheus can reference data larger than RAM
- RSS looks alarmingly high — most is page cache, not working set
- Under memory pressure, OS evicts pages automatically
- Real working set is much smaller than RSS suggests

## Exercises

1. Draw the full TSDB architecture from memory. Include: scrape → WAL → Head → compaction → blocks → mmap.
2. Start `docker run -p 9090:9090 prom/prometheus`, generate some metrics, then `docker exec` into the container and explore `/prometheus/` — find WAL segments, block ULIDs, `meta.json`.
3. Explain why the WAL exists when data is already in memory (the Head block).
4. Calculate: if you have 1M active series scraped every 15s, how many samples per second? At 1.37 bytes/sample compressed, how much memory does 2 hours of Head block data consume?

## Key Takeaways

> "The Head block is an in-memory TSDB with a WAL for durability. Every 2 hours it's flushed to an immutable block on disk. Queries fan out across the Head and all relevant blocks."

> "Gorilla XOR compression achieves ~1.37 bytes per sample because adjacent timestamps have regular intervals and adjacent float values share most bits."

---

## Build — Mini WAL + Gorilla Compression

Implement a write-ahead log and Gorilla XOR compression in any language.

**Part 1 — WAL:**
1. Append-only file writer that serializes `(series_id, timestamp, value)` tuples
2. `append(series_id: u64, timestamp: i64, value: f64)` → writes to file
3. `replay() -> Iterator[(series_id, timestamp, value)]` → reads all records back
4. Segment rotation: start a new file when current exceeds 128 MB

**Part 2 — Gorilla Compression:**
1. Implement delta-of-delta encoding for timestamps:
   - First timestamp: store raw (64 bits)
   - Second: store delta (variable bits)
   - Subsequent: store delta-of-delta (variable bits, 0 = 1 bit)
2. Implement XOR encoding for float64 values:
   - First value: store raw (64 bits)
   - Subsequent: XOR with previous. Store leading zeros count + meaningful bits
3. Write a `Chunk` that compresses a sequence of `(timestamp, value)` pairs
4. Measure compression ratio: target < 2 bytes/sample

**Part 3 — Put Them Together:**
1. Writes go to WAL first, then to in-memory chunks
2. On "flush" (simulating compaction), write chunk to a file on disk
3. Read back: decompress chunk, return samples

**What you'll learn:** Why WAL exists (crash recovery), how Gorilla achieves 12x compression, why the Head block is fast (append-only WAL + in-memory chunks).

---

## Design — In-Memory Time-Series Store

Design a service that stores the last 2 hours of metrics in memory with WAL-backed durability.

**Requirements:**
- Accept samples via HTTP POST: `{metric: "cpu_usage", labels: {pod: "x"}, value: 0.85, timestamp: 1234567890}`
- Store in-memory using compressed chunks (Gorilla)
- WAL on local disk for crash recovery
- Query API: given metric name + label matchers + time range, return matching samples
- Flush to disk every 2 hours as immutable blocks

**Design decisions to make:**
- How do you index series? (label set → fingerprint hash → series struct)
- How do you handle concurrent writes from multiple scrapers?
- What happens during compaction? Can queries still be served?
- How much memory does 1M series at 15s interval for 2 hours consume?
