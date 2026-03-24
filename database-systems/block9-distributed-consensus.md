# Block 9 — Distributed Consensus & Coordination

## Why This Matters

Every distributed observability system needs to answer: how do multiple nodes agree on state? Which node owns which data? What happens when a node dies?

- **Mimir**: consistent hash ring (via etcd/Raft or memberlist/gossip) to route series to ingesters
- **Thanos**: no consensus needed (each component is independent, object storage is the shared state)
- **Kafka** (used by some pipelines): ZooKeeper/KRaft for partition leadership
- **etcd**: Raft consensus for Kubernetes state (including your observability stack's config)

## Raft Consensus

A protocol for a group of nodes to agree on a sequence of operations, even if some nodes fail.

### The Core Idea

One node is the **leader**. All writes go through the leader. The leader replicates to **followers**. A write is committed when a **majority (quorum)** acknowledges it.

```
Client write → Leader
                ├── Replicate to Follower 1 (ack)
                ├── Replicate to Follower 2 (ack)  ← quorum reached (2/3)
                └── Replicate to Follower 3 (slow, doesn't matter)
              Leader commits, responds to client
```

### Leader Election

1. Followers expect periodic heartbeats from the leader
2. If no heartbeat for `election_timeout`: follower becomes **candidate**
3. Candidate requests votes from all nodes
4. Node that gets majority of votes becomes new leader
5. New leader starts sending heartbeats

**Split brain prevention:** A node only votes for one candidate per term. With majority vote required, at most one leader per term.

### Log Replication

- Leader maintains an ordered log of operations
- Each entry has: index, term, command
- Leader sends `AppendEntries` RPCs to followers
- Entry is committed when majority have it
- Committed entries are safe: guaranteed to survive leader changes

### Where Raft Is Used in Observability

| System | Uses Raft For |
|--------|--------------|
| **etcd** | All Kubernetes state, including ServiceMonitors and PrometheusRules |
| **Mimir** (with etcd) | Hash ring state: which ingester owns which token range |
| **CockroachDB** | Distributed SQL (used by some for storing metadata) |
| **Consul** | Service discovery, KV store (Thanos can use for service discovery) |

## Consistent Hashing

The mechanism that distributes data across nodes without a central coordinator.

### Basic Consistent Hashing

```
Hash ring: 0 ────────── 2^32
           │                │
     Node A (token: 100)    │
           │                │
     Node B (token: 500)    │
           │                │
     Node C (token: 800)    │
           └────────────────┘

Series hash("http_requests{pod=x}") = 350
  → Falls between Node A (100) and Node B (500)
  → Assigned to Node B (first node clockwise)
```

### Virtual Nodes (Tokens)

Problem: with 3 nodes, data distribution is uneven.
Solution: each node claims multiple positions on the ring.

```
Node A: tokens [100, 400, 700]
Node B: tokens [200, 500, 900]
Node C: tokens [300, 600, 800]
```

With 128+ virtual nodes per physical node, distribution approaches uniform.

### What Happens When a Node Joins/Leaves

**Node joins:**
1. New node claims tokens on the ring
2. Data that now maps to the new node is migrated from the previous owner
3. Only the data between the new node's tokens and its predecessor needs to move
4. Other nodes are unaffected

**Node leaves (graceful):**
1. Node transfers its data to the next nodes on the ring
2. Tokens are released
3. Successor nodes now own the additional ranges

**Node crashes (ungraceful):**
1. Tokens become "orphaned"
2. Replication factor ensures data still exists on other nodes
3. Ring detects failure (heartbeat timeout), reassigns tokens

### In Mimir

```
remote_write → Distributor
                 ↓
           hash(series labels) → find token on ring → 3 Ingesters
                                    (replication factor 3)
```

- Distributors are stateless — just compute the hash and forward
- Hash ring stored in KV store (etcd) or gossip (memberlist)
- Each Ingester registers tokens when it starts, deregisters on shutdown
- During rolling restart: one Ingester goes down, its tokens are temporarily handled by the next node on the ring, writes are buffered/retried

## CAP Theorem — In Practice, Not Theory

**CAP:** In a network partition, you must choose between Consistency and Availability.

But the real question is: what does each system choose, and what does it mean operationally?

| System | Choice | What It Means |
|--------|--------|---------------|
| **Prometheus** (standalone) | Not distributed — no partition tolerance. CP for local data. | Single node: all reads/writes hit the same process. If it's down, both reads and writes fail. |
| **Mimir** | AP for reads, CP for writes (tunable) | Writes: quorum required (replication factor 3, write to 2). Reads: can read from any replica (eventually consistent). During partition: writes to minority partition fail, reads may return stale data. |
| **Cassandra** | AP by default, tunable to CP | `QUORUM` reads/writes give consistency. `ONE` gives availability. Observability workloads typically use `ONE` for writes (fast) and `QUORUM` for reads (consistent). |
| **etcd** | CP | Strong consistency via Raft. During partition: minority partition can't serve reads or writes. Majority partition continues. |

### What This Means for Operations

**Mimir ingester crash:**
1. Ingester goes down, taking its WAL with it
2. Hash ring detects failure (heartbeat timeout, ~30s)
3. Ring re-routes new writes to next Ingester on ring
4. In-flight writes: lost (unless WAL replay catches them when ingester restarts)
5. Replication factor 3: two other Ingesters have copies of all committed data
6. Query path: Querier detects one replica missing, uses remaining two

**Key operational insight:** Mimir's replication factor determines how many Ingester failures you can tolerate. RF=3 means you can lose 1 Ingester with no data loss for committed writes. Losing 2 Ingesters simultaneously risks data loss.

## Exercises

1. Draw the Mimir hash ring with 3 Ingesters and 9 tokens. Show where a series with hash value 450 gets routed. Then show what happens when Ingester 2 crashes.
2. Explain why Distributors are stateless but Ingesters are stateful. What does this mean for scaling each?
3. A 5-node etcd cluster loses 2 nodes. Can it still serve reads? Writes? What about 3 nodes lost?
4. Compare: Mimir uses consistent hashing, Kafka uses partition assignment via controller. What's the tradeoff?

## Key Takeaways

> "Consistent hashing lets you add or remove nodes without reshuffling all data — only the neighbors of the changed node are affected. This is why Mimir can do rolling restarts of Ingesters without downtime."

> "Raft guarantees that committed entries survive leader changes, but at the cost of availability during partitions. etcd uses Raft, which is why losing a majority of etcd nodes takes down your entire Kubernetes cluster."

---

## Build — Raft Leader Election

Implement the leader election portion of Raft (no log replication needed).

**Requirements:**
1. Model 3-5 nodes as threads or processes communicating via message queues (or channels, or HTTP)
2. Each node has state: `Follower`, `Candidate`, or `Leader`
3. Each node has a `current_term` (monotonically increasing integer)
4. **Heartbeats**: Leader sends heartbeats to all followers every 100ms
5. **Election timeout**: If a Follower doesn't hear from Leader in 300-500ms (randomized), become Candidate
6. **Voting**: Candidate requests votes. Each node votes for at most one candidate per term. Candidate with majority becomes Leader.
7. **Term conflict**: If a node receives a message with a higher term, step down to Follower
8. **Logging**: Print state transitions: `Node 2: Follower → Candidate (term 3)`, `Node 2: Candidate → Leader (term 3)`
9. **Test**: Kill the leader process. Verify a new leader is elected within 1 second.

**Stretch**: Add basic log replication — Leader broadcasts `AppendEntries` with log entries, Followers acknowledge, Leader commits when quorum reached.

**What you'll learn:** Why randomized timeouts prevent split votes, how term numbers resolve conflicts, the cost of leader election (brief unavailability during transition).

---

## Design — Distributed Metrics Ingestion Layer

Design the Distributor + Ingester layer of a Mimir-like system.

**Requirements:**
- Distributors receive remote_write, hash each series to determine which Ingesters own it
- Consistent hash ring with virtual nodes for even distribution
- Replication factor 3: each series written to 3 Ingesters
- Ingesters hold data in memory (Head block) with WAL for durability
- Ingesters periodically flush to object storage (S3)

**Design decisions:**
- What hash function? How many virtual nodes per Ingester?
- How does the ring handle Ingester restarts during rolling update?
- What happens to in-flight writes when an Ingester crashes before flushing?
- How does a new Ingester catch up (does it replay from WAL? From object storage? From other Ingesters?)
- How do you handle the "handoff" period during ring changes — both old and new owners temporarily accept writes?
