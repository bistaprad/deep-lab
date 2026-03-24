# Block 7 — LSM Trees vs B-Trees

## Why This Matters for Observability

Every observability backend is built on one of these two storage models:
- **LSM trees**: Prometheus TSDB, RocksDB (used by CockroachDB, Pebble), Cassandra, LevelDB
- **B-trees**: PostgreSQL, MySQL/InnoDB, SQLite

Understanding the tradeoff explains why Prometheus handles high write throughput but range queries over large datasets can be slow — and why PostgreSQL is great for point lookups but struggles with time-series write rates.

## B-Tree

The default for relational databases. Organized as a balanced tree of pages on disk.

```
         [50]
        /    \
    [20,30]   [70,80]
   / |  \    / |  \
 [10][25][35] [60][75][90]   ← leaf pages contain actual data
```

**Write path:**
1. Find the correct leaf page (O(log n) tree traversal)
2. Write the new value into the page
3. If page is full: split the page, update parent
4. Write-ahead log (WAL) for crash safety

**Read path:**
1. Traverse tree from root to leaf: O(log n) page reads
2. Data is sorted within pages, binary search within page

**Characteristics:**
- Read-optimized: O(log n) for point lookups and range scans
- Write amplification: every update rewrites an entire page (typically 4-16 KB)
- Space amplification: pages can be partially full after splits (~50-70% fill factor)
- In-place updates: modifies data where it lives

## LSM Tree (Log-Structured Merge Tree)

The foundation for write-heavy workloads. Never modifies data in place.

```
Write → Memtable (in-memory, sorted) → Flush → SSTable L0 (disk)
                                                    ↓ compaction
                                               SSTable L1 (disk, merged + sorted)
                                                    ↓ compaction
                                               SSTable L2 (disk, larger, merged)
```

**Write path:**
1. Append to WAL (sequential write, fast)
2. Insert into memtable (in-memory sorted structure, typically a skip list or red-black tree)
3. When memtable is full: flush to disk as an immutable SSTable (Sorted String Table)
4. Background compaction merges SSTables at each level

**Read path:**
1. Check memtable first (most recent data)
2. Check L0 SSTables (may need to check all, they can overlap)
3. Check L1, L2, etc. (each level has non-overlapping key ranges)
4. Use bloom filters to skip SSTables that definitely don't contain the key

**Characteristics:**
- Write-optimized: sequential writes only (append to WAL + memtable insert)
- Read amplification: may need to check multiple levels
- Write amplification: data is rewritten during compaction (typically 10-30x)
- Space amplification: old versions exist until compaction removes them

## The Tradeoff

| | B-Tree | LSM Tree |
|---|--------|----------|
| **Write throughput** | Lower (random I/O, page rewrites) | Higher (sequential I/O, append-only) |
| **Read latency** | Lower (single tree traversal) | Higher (check multiple levels) |
| **Write amplification** | Page-level rewrites | Compaction rewrites (10-30x) |
| **Space amplification** | Moderate (partial pages) | Higher (old versions until compaction) |
| **Compression** | Moderate | Better (SSTables are immutable, compress well) |
| **Ideal for** | Read-heavy, point lookups | Write-heavy, time-series, logs |

## Mapping to Prometheus TSDB

Prometheus TSDB is an **LSM-like** design, adapted for time series:

| LSM Concept | Prometheus Equivalent |
|-------------|----------------------|
| Memtable | Head block (in-memory chunks) |
| WAL | WAL (128MB segments) |
| SSTable flush | Block compaction (every 2 hours) |
| Level compaction | Block merging (2h → 6h → 24h → multi-day) |
| Bloom filters | Posting lists in block index |
| Key | Series fingerprint (label set hash) |
| Value | Compressed (timestamp, value) chunks |

Key difference: Prometheus doesn't use traditional LSM level compaction. It uses **time-based compaction** — blocks covering adjacent time ranges are merged. This is because queries are almost always time-bounded.

## Compaction Strategies

### Size-Tiered Compaction (Cassandra default)
- SSTables of similar size are merged together
- Good write throughput, higher space amplification
- Multiple SSTables can contain overlapping key ranges

### Leveled Compaction (LevelDB, RocksDB default)
- Each level has non-overlapping key ranges
- Better read performance, higher write amplification
- Guarantees at most one SSTable per key range per level

### Time-Window Compaction (Cassandra TWCS, Prometheus blocks)
- Compaction happens within time windows
- Old data is never rewritten with new data
- Ideal for time-series: data naturally partitions by time

## Exercises

1. Draw the write path for both LSM and B-tree. Label where disk I/O occurs and whether it's sequential or random.
2. Explain why Prometheus chose an LSM-like model. What about time-series write patterns makes this a good fit?
3. A system receives 1M writes/sec and serves 100 reads/sec. LSM or B-tree? What about 100 writes/sec and 1M reads/sec?
4. What is write amplification? Calculate approximate write amplification for a 3-level LSM tree with size ratio 10.

## Key Takeaways

> "LSM trees trade read amplification for write throughput. B-trees trade write amplification for read latency. Prometheus chose LSM-like design because time-series workloads are overwhelmingly write-heavy: millions of samples/sec ingested, queries are relatively rare."

> "Compaction is the hidden cost of LSM trees. It's CPU and I/O intensive, runs in the background, and can cause latency spikes if it falls behind. This is why Prometheus compaction settings matter for production stability."

---

## Build — Mini LSM Tree

Implement a simplified LSM tree key-value store.

**Requirements:**
1. **Memtable**: in-memory sorted map (red-black tree, skip list, or just a sorted dict)
2. **WAL**: append-only file. Every write goes to WAL before memtable.
3. **Flush**: when memtable exceeds size threshold (e.g., 4 MB), write it to disk as a sorted SSTable file
4. **SSTable format**: sorted key-value pairs + an index (key → file offset) at the end of the file
5. **Read path**: check memtable → check SSTables from newest to oldest → return first match
6. **Bloom filter** (stretch): per-SSTable bloom filter to skip SSTables that definitely don't contain the key
7. **Compaction** (stretch): merge two SSTables at the same level into one sorted SSTable at the next level

**Benchmark:** Insert 1M key-value pairs, then read 10,000 random keys. Measure write throughput and read latency. Compare with and without bloom filters.

**What you'll learn:** Why LSM writes are fast (sequential I/O), why reads can be slow (multiple SSTables), how bloom filters eliminate unnecessary disk reads, how compaction works.

---

## Design — Log Storage Backend

Design a log storage system for an observability platform (like a simplified Loki).

**Requirements:**
- Ingest structured log entries: `{timestamp, labels: {service, pod, level}, message}`
- Store using LSM-tree architecture: WAL → memtable → SSTable/chunks on disk
- Index by labels (inverted index) but store log lines as compressed chunks
- Query: given label matchers + time range, return matching log lines
- Retention: automatically delete data older than N days

**Design decisions:**
- How do you partition data? By time? By label hash? Both?
- What compression do you use for log chunks? (Snappy for speed? Zstd for ratio?)
- How do you handle queries that scan large time ranges? (Parallel chunk reads? Index caching?)
- How does this differ from a time-series metric store? (Variable-size messages vs fixed-size samples)
