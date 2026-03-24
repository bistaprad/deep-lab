# Learning Plan Thread Summary

## What Was Built

A comprehensive, self-paced reading plan in `/Users/pradeepbista/learning/` covering 5 domains across 26 blocks.

### Directory Structure

```
/Users/pradeepbista/learning/
├── READING_PLAN.md              # Master plan with all blocks, checklists, self-assessments
├── prometheus/                   # Domain A — Blocks 1-6
│   ├── block1-data-model.md
│   ├── block2-tsdb-engine.md
│   ├── block3-index-queries.md
│   ├── block4-scraping-remote-write.md
│   ├── block5-scaling.md
│   └── block6-promql.md
├── database-systems/             # Domain B — Blocks 7-10
│   ├── block7-lsm-vs-btree.md
│   ├── block8-columnar-vs-row.md
│   ├── block9-distributed-consensus.md
│   └── block10-tsdb-patterns.md
├── ai-monitoring/                # Domain C — Blocks 11-15
│   ├── block11-ai-observability-intro.md
│   ├── block12-llm-tracing.md
│   ├── block13-evals.md
│   ├── block14-infra-metrics.md
│   └── block15-tool-landscape.md
├── observability-security/       # Domain D — Blocks 16-20
│   ├── block16-ebpf-observability.md
│   ├── block17-profiling-slos.md
│   ├── block18-pipelines-closed-loop.md
│   ├── block19-threat-model-injection.md
│   └── block20-security-synthesis.md
└── agentic-systems/              # Domain E — Blocks 21-26
    ├── block21-reasoning-loop.md
    ├── block22-context-management.md
    ├── block23-multi-agent-orchestration.md
    ├── block24-agent-security-guardrails.md
    ├── block25-framework-synthesis.md
    └── block26-autonomous-agent-platforms.md
```

### Domains & Blocks

**Domain A — Prometheus & TSDB Internals (Blocks 1-6)**
- Block 1: Data model, metric types (Counter, Gauge, Histogram, Summary), cardinality
- Block 2: TSDB storage engine — Head block, WAL, compaction, Gorilla XOR compression
- Block 3: On-disk index, posting lists, query execution path
- Block 4: Scraping, remote write, staleness markers, queue mechanics
- Block 5: Horizontal scaling — Thanos, Mimir, VictoriaMetrics comparison
- Block 6: PromQL deep dive — rate(), irate(), histogram_quantile(), recording rules

**Domain B — Database & Distributed Systems (Blocks 7-10)**
- Block 7: LSM trees vs B-trees — write amplification, read amplification, compaction
- Block 8: Columnar vs row-oriented storage — ClickHouse, compression, vectorized execution
- Block 9: Distributed consensus — Raft, consistent hashing, CAP theorem
- Block 10: TSDB design patterns — downsampling, multi-resolution, format comparison

**Domain C — AI Pipeline Monitoring (Blocks 11-15)**
- Block 11: Four layers of AI observability (infra, tracing, eval, behavioral)
- Block 12: LLM tracing with OpenTelemetry GenAI semconv and LangFuse
- Block 13: Output quality evaluation — LLM-as-judge, evals in CI
- Block 14: Infrastructure metrics for AI — GPU, TTFT, TPOT, token throughput
- Block 15: Tool landscape — LangFuse, LangSmith, Arize Phoenix, decision framework

**Domain D — Emerging Observability & AI Security (Blocks 16-20)**
- Block 16: eBPF — kprobes, uprobes, Cilium Hubble, Pixie, Grafana Beyla
- Block 17: Continuous profiling (Pyroscope, Parca) + SLO-driven alerting (burn rate, Sloth)
- Block 18: Observability pipelines (OTEL Collector, Alloy) + closed-loop vision
- Block 19: AI threat model — prompt injection (direct/indirect), jailbreaking, OWASP LLM Top 10
- Block 20: Agent security architecture — PREVENT/DETECT/RESPOND, K8s security, RBAC

**Domain E — Agentic Systems Engineering (Blocks 21-26)**
- Block 21: The reasoning loop — ReAct, Plan-Execute, Reflexion, CoT. Build ReAct from scratch.
- Block 22: Context management — sliding window, anchored summarization, context folding (10x compression), hierarchical memory, context drift
- Block 23: Multi-agent orchestration — supervisor, pipeline, parallel, debate, event-driven. Structured handoffs, circuit breakers.
- Block 24: Agent security — sandboxing (Firecracker, gVisor), deny-by-default guardrails, data isolation between agents, audit trails
- Block 25: Framework synthesis — building a complete agentic framework (~500 lines), comparing LangChain/CrewAI/AutoGen, open challenges (eval, debugging, cost, reliability)
- Block 26: General-purpose autonomous agent platforms — OpenClaw (327k-star personal agent, gateway architecture, multi-channel), Manus AI (CodeAct pattern, autonomous execution, Meta acquisition), NVIDIA Agent Toolkit/NemoClaw (enterprise security via OpenShell, hardware-isolated sandboxes, Nemotron models). Three distribution models: personal infrastructure, delegated service, enterprise middleware.

### Every Block Has Three Sections

1. **Read** — Primary sources, papers, docs, code
2. **Build** — Hands-on coding exercise (any language). Examples:
   - Block 1: Metrics library with Counter/Gauge/Histogram + Prometheus exposition format
   - Block 7: Mini LSM tree key-value store with WAL, SSTables, bloom filters
   - Block 21: ReAct agent from scratch using Claude API
   - Block 24: Agent security middleware with policy engine and audit logging
3. **Design** — System design exercise. Examples:
   - Block 1: Cardinality analysis service
   - Block 7: Log storage backend (simplified Loki)
   - Block 23: General-purpose multi-agent orchestration platform
   - Block 25: Production agent platform at enterprise scale

### User Preferences

- **No interview prep language** — this is for internal growth and learning, not prepping
- **Block-based, not daily** — no time commitments, go at your own pace
- **Quizzing available** — the user requested to be quizzed/interviewed on topics as they go through them. Structure: warm-up recall → application scenarios → design/tradeoff questions
- **Each domain has a self-assessment** section at the end with 4-6 questions

### Quizzing Format (Agreed Upon, Not Yet Started)

When the user is ready to be quizzed on any block:
1. **Warm-up** (2-3 recall questions) — core concepts
2. **Application** (2-3 scenario questions) — real situations
3. **Design/Tradeoff** (1-2 hard questions) — defend decisions, compare approaches

### Progress Tracking & Retention Analytics (Added)

Four new files support progress tracking with time-series retention data:

- `PROGRESS.md` — Daily dashboard: block completion tables per domain, confidence scores, domain rollup scores
- `review_log.csv` — Raw time-series data. One row per review event with 13 columns: date, block_id, block_name, domain, review_type, days_since_completion, days_since_last_review, time_spent_minutes, questions_attempted, questions_recalled, confidence_before, confidence_after, gaps
- `REVIEW_LOG_SCHEMA.md` — Column definitions, example rows, 8 analytics queries (retention curves, decay rates, domain difficulty, confidence calibration, learning velocity, etc.), pandas quick-load snippet
- `review_check.py` — CLI tool that reads `review_log.csv` and prints today's study agenda: what reviews are due, what's overdue, what's coming up in 3 days, completion summary

**Daily workflow:**
1. Run `python3 review_check.py` to see what's due
2. Do due reviews (5-15 min each)
3. Work on next block
4. Append one row to `review_log.csv` after each session

**Review cadence:** 3-day recall (5 min) → 10-day application (15 min) → 30-day cold check (10 min) → domain rollup after all blocks in domain reviewed.

**Domain rollup score:** Attempt all self-assessment questions (from READING_PLAN.md) with no notes. Score = correct / total. Below 50% → revisit the blocks behind the missed questions.

**Key analytics enabled:**
- Retention decay curve per block and per domain
- Recall rate over time (`questions_recalled / questions_attempted`)
- Confidence calibration (are you over/underconfident?)
- Time investment vs retention correlation
- Learning velocity (do later blocks take less time?)
- Review effectiveness (`confidence_after - confidence_before`)

### Learning Philosophy (Restructured)

The plan was restructured based on insights from experienced builders:

- **Dan Luu** ([What to Learn](https://danluu.com/learn-what/)): Master a few tricks. Even Hilbert relied on the same handful of techniques. Don't learn everything — get devastating at the few skills natural to you.
- **Martin Kleppmann** ([DDIA](https://dataintensive.net/)): Learn the tradeoff, not the tool. Software changes; fundamental tensions don't.
- **Julia Evans** ([jvns.ca](https://jvns.ca/)): Build small, poke until you understand. "You have to learn something. It doesn't have to work."
- **Ben Kuhn** ([Conviction](https://www.benkuhn.net/conviction/)): Judgment comes from doing, not reading. You build conviction by making hard decisions and calibrating.
- **Patrick Collison** ([Advice](https://patrickcollison.com/advice)): Go deep. Make things. Find great practitioners.

**New file:** `LEARNING_PHILOSOPHY.md` — full restructured plan with three tiers, learning sequence, and write-up library spec.

**Three Rules:**
1. Learn the tradeoff, not the tool
2. Build small, break fast
3. Skip what you can learn in a week when you need it

**Three Tiers:**
- **Tier 1 (Build Judgment):** Blocks 21, 22, 24, 11 — read, build, break, write. Full review tracking.
- **Tier 2 (Know the Landscape):** Blocks 23, 25, 26, 12, 13, 14, 19, 9, 7 — read + write the one tradeoff. Log completion only.
- **Tier 3 (Know It Exists):** Blocks 6, 8, 10, 15, 16, 17, 18, 20 — skim, 3-sentence summary, no tracking.
- **Deferred:** Blocks 1-5 — already operational knowledge.

**Write-Up Library:** Each block produces a written artifact (1 page max) stored in `writeups/`. These serve as personal reference, design review material, and proof of understanding.

**Communication:** "Speak" exercises replaced with "Write" exercises — produce clear, precise 1-page explanations that sharpen technical communication.

### Previous Thread References

- Original conversation: [Learning Plan Creation](1246dab6-cb08-450b-b8ac-7fa084be2ad1)
- Progress tracking & improvements: [Learning Plan Improvements](d78b56c4-8970-4daa-8285-b9e0fe87aaed)
