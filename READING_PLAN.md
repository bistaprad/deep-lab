# Deep Dive Reading Plan

**Domains:** Prometheus Internals, Database & Distributed Systems, AI Pipeline Monitoring, Emerging Observability & Security, Agentic Systems Engineering

---

## How to Use This Plan

The plan is organized into **blocks**, not days. Each block is a self-contained topic. Work through them at whatever pace makes sense — one block might take an evening, another might take a few sessions.

Each block has three parts:
- **Read**: primary sources — papers, docs, code.
- **Do**: hands-on exercises that force internalization.
- **Speak**: practice articulating the concept clearly. Record yourself or explain to someone.

After each domain there is a self-assessment. If you can't answer the questions without notes, revisit the relevant block.

---

## Domain A — Prometheus & TSDB Internals

> Move from "I've operated Prometheus at scale" to "I can explain exactly what happens inside the engine."

### Block 1 — Data Model & Metric Types
- [ ] **Read** `prometheus/block1-data-model.md`
- [ ] **Read** Prometheus docs: [Data Model](https://prometheus.io/docs/concepts/data_model/) and [Metric Types](https://prometheus.io/docs/concepts/metric_types/)
- [ ] **Do**: On paper, draw the relationship between metric name, label set, fingerprint, and time series. No references.
- [ ] **Do**: Write down 3 examples each of Counter, Gauge, Histogram, Summary from your own operational experience.
- [ ] **Speak**: Explain why histograms are preferred over summaries at scale. Target: 90 seconds, no notes.

### Block 2 — TSDB Storage Engine
- [ ] **Read** `prometheus/block2-tsdb-engine.md`
- [ ] **Read** Fabian Reinartz's TSDB design doc: https://fabxc.org/tsdb/
- [ ] **Read** Ganesh Vernekar's blog: https://ganeshvernekar.com/blog/prometheus-tsdb-the-head-block/
- [ ] **Do**: Draw the full TSDB architecture from memory: Head block → WAL → compaction → on-disk blocks → mmap. Include Gorilla XOR encoding.
- [ ] **Do**: Start a local Prometheus (`docker run prom/prometheus`), ingest metrics, explore the `data/` directory — find WAL segments, block directories, `meta.json`, `chunks/`, `index`.
- [ ] **Speak**: Walk through what happens when a sample arrives, from scrape to on-disk storage. Target: 3 minutes.

### Block 3 — On-Disk Index & Query Execution
- [ ] **Read** `prometheus/block3-index-queries.md`
- [ ] **Read** Ganesh Vernekar: https://ganeshvernekar.com/blog/prometheus-tsdb-persistent-block-and-its-index/
- [ ] **Do**: Trace a query on paper: `http_requests_total{status="200", method="GET"}` → posting list lookup → intersection → chunk seek → decompress → filter → return.
- [ ] **Do**: Use `promtool tsdb dump` on your local Prometheus data directory.
- [ ] **Speak**: Explain why high label cardinality hurts query performance. Connect to posting list intersection. Target: 2 minutes.

### Block 4 — Scraping, Remote Write, Staleness
- [ ] **Read** `prometheus/block4-scraping-remote-write.md`
- [ ] **Read** Prometheus docs: [scrape_config](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config) and [remote_write](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_write)
- [ ] **Do**: Configure Prometheus to scrape a local app and remote_write to a second instance. Observe WAL behavior.
- [ ] **Do**: Kill a scrape target and observe stale markers using `promtool tsdb dump`.
- [ ] **Speak**: Explain remote_write queue mechanics: capacity, shards, backpressure, sample drops. Target: 2 minutes.

### Block 5 — Horizontal Scaling: Thanos & Mimir
- [ ] **Read** `prometheus/block5-scaling.md`
- [ ] **Read** Thanos quick tutorial: https://thanos.io/tip/thanos/quick-tutorial.md/
- [ ] **Read** Mimir architecture: https://grafana.com/docs/mimir/latest/get-started/about-grafana-mimir-architecture/
- [ ] **Do**: Draw Thanos architecture from memory, then Mimir. Compare the two diagrams.
- [ ] **Do**: Write a 1-page comparison: Thanos vs Mimir vs VictoriaMetrics — pros, cons, when to choose.
- [ ] **Speak**: Tell the story of your 30M→3M cardinality reduction: problem, approach, tooling, results, organizational challenge. Target: 4 minutes.

### Block 6 — PromQL Deep Dive
- [ ] **Read** `prometheus/block6-promql.md`
- [ ] **Read** PromQL docs: https://prometheus.io/docs/prometheus/latest/querying/basics/
- [ ] **Do**: Write 10 PromQL queries from scratch (see the practice list in the block file).
- [ ] **Do**: Explain `rate()` internals out loud: first/last sample, counter reset handling, minimum 2 samples.
- [ ] **Speak**: Given "API latency is spiking for one endpoint" — write the PromQL live and explain each function. Practice 3 times.

### Domain A — Self-Assessment
1. What is Gorilla XOR compression and why does it work well for time series?
2. Walk through the lifecycle of a sample from scrape to on-disk block.
3. How does the inverted index enable fast label-based queries?
4. What happens when a Prometheus remote_write queue fills up?
5. Explain the Mimir write path from remote_write to object storage.
6. Why did you choose Grafana Cloud over VictoriaMetrics? What were the tradeoffs?

---

## Domain B — Database & Distributed Systems

> Understand the storage engines and distributed patterns underneath every observability tool you use.

### Block 7 — LSM Trees vs B-Trees
- [ ] **Read** `database-systems/block7-lsm-vs-btree.md`
- [ ] **Read** "Designing Data-Intensive Applications" Chapter 3 (Storage and Retrieval) — or the LSM tree paper: https://www.cs.umb.edu/~poneil/lsmtree.pdf
- [ ] **Read** RocksDB architecture: https://github.com/facebook/rocksdb/wiki/RocksDB-Overview
- [ ] **Do**: Draw write path and read path for both LSM tree and B-tree from memory. Label where write amplification and read amplification occur.
- [ ] **Do**: Map Prometheus TSDB to the LSM model: Head block = memtable, compaction = merge, blocks = sorted runs.
- [ ] **Speak**: Explain the LSM vs B-tree tradeoff: write-optimized vs read-optimized. When would you choose each? Target: 3 minutes.

### Block 8 — Columnar vs Row-Oriented Storage
- [ ] **Read** `database-systems/block8-columnar-vs-row.md`
- [ ] **Read** ClickHouse architecture overview: https://clickhouse.com/docs/en/development/architecture
- [ ] **Read** "The Design and Implementation of Modern Column-Oriented Database Systems" (Abadi et al.) — intro + Chapter 2
- [ ] **Do**: For three real systems you use (ClickHouse, PostgreSQL, Prometheus TSDB), classify as row/column/hybrid and explain why that orientation was chosen.
- [ ] **Do**: Write a query that would be fast on columnar storage and slow on row storage, and vice versa. Explain why.
- [ ] **Speak**: Explain why LangFuse uses ClickHouse for trace analytics. What makes columnar storage ideal for observability? Target: 2 minutes.

### Block 9 — Distributed Consensus & Coordination
- [ ] **Read** `database-systems/block9-distributed-consensus.md`
- [ ] **Read** Raft paper (condensed): https://raft.github.io/
- [ ] **Read** Consistent hashing explained: https://www.toptal.com/big-data/consistent-hashing
- [ ] **Do**: Draw how Mimir's hash ring distributes series across ingesters. Show what happens when an ingester fails and a new one joins.
- [ ] **Do**: Explain the CAP tradeoff for three systems: Prometheus (single-node), Mimir (distributed), Cassandra.
- [ ] **Speak**: What consistency guarantees does Mimir provide for writes vs reads? What happens during an ingester crash? Target: 2 minutes.

### Block 10 — Time-Series Database Design Patterns
- [ ] **Read** `database-systems/block10-tsdb-patterns.md`
- [ ] **Read** InfluxDB IOx architecture: https://docs.influxdata.com/influxdb/cloud-dedicated/reference/internals/
- [ ] **Read** TimescaleDB vs InfluxDB vs Prometheus comparison (any recent benchmark article)
- [ ] **Do**: Compare storage formats: Prometheus TSDB, InfluxDB IOx (Apache Parquet), TimescaleDB (PostgreSQL extension), VictoriaMetrics. Create a comparison table: compression ratio, write speed, query latency, retention strategy.
- [ ] **Do**: Design a TSDB for a specific workload: 10M series, 15s scrape interval, 90-day retention, sub-second p99 queries. Which architecture would you choose and why?
- [ ] **Speak**: Explain downsampling: why it exists, how Thanos/Mimir implement it, and the tradeoff between resolution and storage cost. Target: 2 minutes.

### Domain B — Self-Assessment
1. Explain the LSM tree write path. Where does write amplification come from?
2. Why is columnar storage faster for `SELECT avg(latency) FROM traces WHERE status='error'`?
3. What happens to Mimir's hash ring when an ingester crashes? How are in-flight writes recovered?
4. Compare Prometheus TSDB, ClickHouse, and TimescaleDB for storing observability data. When would you use each?
5. What is the CAP tradeoff and what does Mimir choose?

---

## Domain C — AI Pipeline Monitoring

> Speak concretely about production AI observability with real tooling knowledge.

### Block 11 — Why AI Monitoring Is Different + The Four Layers
- [ ] **Read** `ai-monitoring/block11-ai-observability-intro.md`
- [ ] **Read** Anthropic's research on monitoring: https://alignment.anthropic.com/2025/summarization-for-monitoring/
- [ ] **Do**: Write a 1-page doc: "Four Layers of AI Observability" with concrete examples from your crash triage agent at each layer.
- [ ] **Speak**: Explain why traditional APM misses the most important AI failure modes. Give 3 specific examples. Target: 2 minutes.

### Block 12 — LLM Tracing with OpenTelemetry + LangFuse
- [ ] **Read** `ai-monitoring/block12-llm-tracing.md`
- [ ] **Read** OpenTelemetry GenAI semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- [ ] **Read** LangFuse docs: https://langfuse.com/docs
- [ ] **Do**: Set up LangFuse locally. Instrument a Claude API call with the LangFuse Python SDK. View the trace.
- [ ] **Do**: Add tool call child spans. Verify the full call chain renders.
- [ ] **Speak**: Describe the OTEL GenAI semantic conventions. What attributes matter and why? Target: 2 minutes.

### Block 13 — Output Quality Evaluation (LLM-as-Judge)
- [ ] **Read** `ai-monitoring/block13-evals.md`
- [ ] **Read** Anthropic eval guide: https://docs.anthropic.com/en/docs/build-with-claude/develop-tests
- [ ] **Do**: Write an LLM-as-judge eval for 5 crash triage test cases. Define the rubric. Run it. Examine scores.
- [ ] **Do**: Run the judge twice on the same cases. Measure score variance.
- [ ] **Speak**: Explain LLM-as-judge pitfalls (positivity bias, self-preference). How do you mitigate? Target: 2 minutes.

### Block 14 — Infrastructure Metrics for AI Workloads
- [ ] **Read** `ai-monitoring/block14-infra-metrics.md`
- [ ] **Read** NVIDIA DCGM exporter: https://github.com/NVIDIA/dcgm-exporter
- [ ] **Read** vLLM metrics: https://docs.vllm.ai/en/latest/serving/metrics.html
- [ ] **Do**: List 10 metrics for LLM inference. For each: name, what it measures, alert threshold, why it matters.
- [ ] **Do**: Define 5 agentic-specific metrics for your crash triage agent with alert thresholds.
- [ ] **Speak**: Explain TTFT vs TPOT. Why does TTFT increase with context length? What dominates TPOT? Target: 90 seconds.

### Block 15 — Tool Landscape Decision Framework
- [ ] **Read** `ai-monitoring/block15-tool-landscape.md`
- [ ] **Do**: Fill out the decision matrix for your agent: which tool at each layer and why?
- [ ] **Do**: Write a 1-page architecture doc: "Observability Stack for Crash Triage Agent" — LangFuse + Prometheus + Grafana.
- [ ] **Speak**: Someone asks "How would you monitor an AI agent in production?" Give a structured 5-minute answer covering all 4 layers.

### Domain C — Self-Assessment
1. What are the four layers of AI observability? Give one concrete metric at each.
2. What OTEL attributes would you capture for every LLM call?
3. Design an LLM-as-judge rubric for a summarization task. What are the pitfalls?
4. What is TTFT and why does it matter for user experience?
5. Why LangFuse over LangSmith for your use case?

---

## Domain D — Emerging Observability & AI Security

> The closed-loop vision: observability as a feedback system that makes software better. Plus the security model for AI systems.

### Block 16 — eBPF & Kernel-Level Observability
- [ ] **Read** `observability-security/block16-ebpf-observability.md`
- [ ] **Read** Brendan Gregg's eBPF overview: https://www.brendangregg.com/ebpf.html
- [ ] **Read** Cilium Hubble docs: https://docs.cilium.io/en/latest/observability/hubble/
- [ ] **Read** Pixie docs (now part of New Relic): https://docs.px.dev/
- [ ] **Do**: Explain the eBPF execution model: bytecode verified at load time, runs in kernel, no kernel module. Draw the data flow from kernel event → eBPF program → user-space map → Prometheus exporter.
- [ ] **Do**: Compare traditional instrumentation (SDK in app code) vs eBPF-based (kernel-level, no code changes). Write a tradeoff table.
- [ ] **Speak**: Explain why eBPF is the biggest shift in telemetry collection in a decade. Target: 2 minutes.

### Block 17 — Continuous Profiling & SLO-Driven Alerting
- [ ] **Read** `observability-security/block17-profiling-slos.md`
- [ ] **Read** Pyroscope docs: https://grafana.com/docs/pyroscope/latest/
- [ ] **Read** Google SRE Book Chapter 4 (SLOs): https://sre.google/sre-book/service-level-objectives/
- [ ] **Read** Sloth (SLO generator): https://sloth.dev/
- [ ] **Do**: Explain the "four pillars" of observability: metrics, logs, traces, profiles. Why is continuous profiling the newest addition?
- [ ] **Do**: Design an SLO for your crash triage agent: what's the SLI, what's the target, how do you compute error budget burn rate?
- [ ] **Speak**: Explain burn-rate alerting vs threshold alerting. Why is burn-rate better for on-call? Target: 2 minutes.

### Block 18 — Observability Pipelines & the Closed-Loop Vision
- [ ] **Read** `observability-security/block18-pipelines-closed-loop.md`
- [ ] **Read** OpenTelemetry Collector architecture: https://opentelemetry.io/docs/collector/
- [ ] **Read** Grafana Alloy docs: https://grafana.com/docs/alloy/latest/
- [ ] **Do**: Draw the observability pipeline: sources → collection (OTEL Collector / Alloy) → processing (filter, transform, route) → backends (Prometheus, Loki, Tempo, ClickHouse). Label where cost reduction happens.
- [ ] **Do**: Design a closed-loop system: observability signals → automated analysis → remediation action → verification. Map your crash triage agent onto this loop.
- [ ] **Speak**: Explain the difference between observability-driven development and traditional monitoring. Give a concrete example using canary deployments. Target: 3 minutes.

### Block 19 — AI Threat Model & Prompt Injection
- [ ] **Read** `observability-security/block19-threat-model-injection.md`
- [ ] **Read** Indirect prompt injection paper: https://arxiv.org/abs/2302.12173
- [ ] **Read** OWASP LLM Top 10: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- [ ] **Do**: Attempt to inject your own agent in a test environment. Document 3 attempts and results.
- [ ] **Do**: Implement structural separation defenses. Re-test.
- [ ] **Speak**: Explain indirect prompt injection with a concrete example from your agent. Why harder than direct? Target: 3 minutes.

### Block 20 — Agent Security Architecture (PREVENT / DETECT / RESPOND)
- [ ] **Read** `observability-security/block20-security-synthesis.md`
- [ ] **Read** MITRE ATLAS: https://atlas.mitre.org/
- [ ] **Do**: Write the RBAC policy and NetworkPolicy for your agent pod.
- [ ] **Do**: Write a 2-page "AI Agent Security Posture" document covering PREVENT, DETECT, RESPOND.
- [ ] **Do**: Test yourself — answer these 5 questions out loud, no notes:
  1. How would you detect indirect prompt injection against your agent?
  2. Walk through the security architecture of your crash triage agent.
  3. What happens when the Claude model version updates?
  4. How does your agent prevent data exfiltration?
  5. What's your incident response plan if injection is detected?

### Domain D — Self-Assessment
1. Explain how eBPF captures network telemetry without application code changes.
2. Design an SLO for your crash triage agent. What's the SLI? The error budget?
3. Draw the closed-loop: telemetry → analysis → action → verification. Where does your agent fit?
4. Explain indirect prompt injection with a concrete attack on your agent.
5. What are the PREVENT, DETECT, RESPOND layers? Give two controls at each.

---

## Domain E — Agentic Systems Engineering

> Build agent frameworks from scratch. Understand the reasoning loop, context management, multi-agent orchestration, and security — not as a user of LangChain, but as someone who could implement it.

### Block 21 — The Reasoning Loop: Building ReAct from Scratch
- [ ] **Read** `agentic-systems/block21-reasoning-loop.md`
- [ ] **Read** ReAct paper: https://arxiv.org/abs/2210.03629
- [ ] **Read** Anthropic tool use docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview
- [ ] **Do**: Implement a ReAct agent from scratch (~100 lines) using only the Claude API. No frameworks.
- [ ] **Do**: Trace through 5 iterations of the agent loop on paper for a real task. Write out every Thought/Action/Observation.
- [ ] **Speak**: Explain ReAct in 90 seconds. What specific problem does the observation step solve that chain-of-thought alone cannot?

### Block 22 — Context Management & Memory
- [ ] **Read** `agentic-systems/block22-context-management.md`
- [ ] **Read** Context Folding paper: https://openreview.net/pdf/fe41fe15d810a14fcba0e47265949390eec8207e.pdf
- [ ] **Do**: Build an adaptive context manager: token counting, result truncation, anchored summarization, memory retrieval.
- [ ] **Do**: Run a 20-iteration simulated agent loop with 5K-token tool results. Verify context stays within golden window.
- [ ] **Speak**: Explain context drift vs context exhaustion. Why is drift the bigger problem? Target: 2 minutes.

### Block 23 — Multi-Agent Orchestration
- [ ] **Read** `agentic-systems/block23-multi-agent-orchestration.md`
- [ ] **Read** AutoGen paper: https://arxiv.org/abs/2308.08155
- [ ] **Read** LangGraph docs: https://langchain-ai.github.io/langgraph/
- [ ] **Do**: Build a supervisor-based multi-agent investigation system: supervisor → parallel analysts → synthesizer.
- [ ] **Do**: Compare supervisor vs pipeline vs parallel for a 3-step task. Measure latency, cost, quality.
- [ ] **Speak**: You have 4 agents. Draw the orchestration pattern on a whiteboard. Explain the handoff protocol between two of them. Target: 3 minutes.

### Block 24 — Agent Security: Sandboxing, Guardrails, Data Isolation
- [ ] **Read** `agentic-systems/block24-agent-security-guardrails.md`
- [ ] **Read** Guardplane: https://github.com/lhy0718/Guardplane
- [ ] **Read** OWASP Top 10 for LLM Applications (revisit LLM01, LLM07, LLM08 with agent focus): https://owasp.org/www-project-top-10-for-large-language-model-applications/
- [ ] **Do**: Build a security middleware: deny-by-default policy engine, tool sandboxing, output scanning, audit logging.
- [ ] **Do**: Red-team your own middleware: attempt disallowed tool calls, injection via tool results, secret exfiltration. Verify all are caught.
- [ ] **Speak**: Explain deny-by-default vs allow-list-based security for agents. Why is deny-by-default the only safe option? Target: 2 minutes.

### Block 25 — Synthesis: Building an Agentic Framework
- [ ] **Read** `agentic-systems/block25-framework-synthesis.md`
- [ ] **Do**: Build a minimal agentic framework (~500 lines): agent definition, 2 reasoning strategies, context management, tool layer, security, workflow DAGs, observability.
- [ ] **Do**: Define and run a 3-agent crash investigation workflow end-to-end.
- [ ] **Speak**: Compare LangChain, CrewAI, and AutoGen. What do they have in common? Where do they differ? Which would you use and when? Target: 3 minutes.

### Block 26 — General-Purpose Autonomous Agent Platforms (OpenClaw, Manus, NVIDIA)
- [ ] **Read** `agentic-systems/block26-autonomous-agent-platforms.md`
- [ ] **Read** OpenClaw repo + README: https://github.com/openclaw/openclaw
- [ ] **Read** OpenClaw architecture docs: https://github.com/openclaw/openclaw/tree/main/docs
- [ ] **Read** NVIDIA NemoClaw announcement: https://nvidianews.nvidia.com/news/ai-agents
- [ ] **Read** NVIDIA OpenShell: https://github.com/NVIDIA/OpenShell
- [ ] **Read** Manus architecture deep dive: https://medium.com/@pankaj_pandey/inside-manus-the-architecture-that-replaced-tool-calls-with-executable-code-d89e1caea678
- [ ] **Read** Anthropic agent autonomy research: https://www.anthropic.com/research/measuring-agent-autonomy
- [ ] **Do**: Install and run OpenClaw locally. Connect WebChat. Trace a message from channel → gateway → agent → tool → response. Document the architecture.
- [ ] **Do**: Compare security models across the three platforms. Write a 1-page tradeoff analysis for deploying a crash triage agent on each.
- [ ] **Do**: Map all three platforms to the Block 25 framework layers. Identify where each invests most.
- [ ] **Speak**: Someone asks "What's the difference between OpenClaw, Manus, and NVIDIA's agent platform?" Give a structured 3-minute answer covering architecture, security model, and target user.

### Domain E — Self-Assessment
1. Explain the ReAct loop in 3 sentences. What specific problem does the observe step solve?
2. Your agent is at 85K tokens in a 100K window. Three strategies to keep going without losing findings.
3. Draw a 4-agent orchestration. What's the handoff protocol? What happens when one agent fails?
4. An attacker injects instructions through a tool result. How does your security layer prevent this?
5. Design an evaluation pipeline for comparing agent v2 vs v1. What metrics? How do you handle non-determinism?
6. Your agent costs $8 per investigation. How do you get it under $2 without destroying quality?
7. Compare OpenClaw, Manus, and NVIDIA NemoClaw. What architectural decision does each make about where the agent runs, and what are the security implications?

---

## Primary Reading Sources

| # | Source | Domain | Block |
|---|--------|--------|-------|
| 1 | [Prometheus TSDB design (Fabian Reinartz)](https://fabxc.org/tsdb/) | Prometheus | 2 |
| 2 | [TSDB Head Block (Ganesh Vernekar)](https://ganeshvernekar.com/blog/prometheus-tsdb-the-head-block/) | Prometheus | 2 |
| 3 | [TSDB Persistent Block & Index](https://ganeshvernekar.com/blog/prometheus-tsdb-persistent-block-and-its-index/) | Prometheus | 3 |
| 4 | [Thanos Quick Tutorial](https://thanos.io/tip/thanos/quick-tutorial.md/) | Prometheus | 5 |
| 5 | [Mimir Architecture](https://grafana.com/docs/mimir/latest/get-started/about-grafana-mimir-architecture/) | Prometheus | 5 |
| 6 | [LSM Tree Paper](https://www.cs.umb.edu/~poneil/lsmtree.pdf) | Database | 7 |
| 7 | [ClickHouse Architecture](https://clickhouse.com/docs/en/development/architecture) | Database | 8 |
| 8 | [Raft Consensus](https://raft.github.io/) | Database | 9 |
| 9 | [Anthropic Hierarchical Summarization](https://alignment.anthropic.com/2025/summarization-for-monitoring/) | AI Monitoring | 11 |
| 10 | [OpenTelemetry GenAI Semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) | AI Monitoring | 12 |
| 11 | [LangFuse Docs](https://langfuse.com/docs) | AI Monitoring | 12 |
| 12 | [Brendan Gregg eBPF](https://www.brendangregg.com/ebpf.html) | Emerging Obs | 16 |
| 13 | [Google SRE Book — SLOs](https://sre.google/sre-book/service-level-objectives/) | Emerging Obs | 17 |
| 14 | [OTEL Collector Architecture](https://opentelemetry.io/docs/collector/) | Emerging Obs | 18 |
| 15 | [Indirect Prompt Injection Paper](https://arxiv.org/abs/2302.12173) | Security | 19 |
| 16 | [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | Security | 19 |
| 17 | [MITRE ATLAS](https://atlas.mitre.org/) | Security | 20 |
| 18 | [ReAct Paper](https://arxiv.org/abs/2210.03629) | Agents | 21 |
| 19 | [Anthropic Tool Use Docs](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) | Agents | 21 |
| 20 | [Context Folding Paper](https://openreview.net/pdf/fe41fe15d810a14fcba0e47265949390eec8207e.pdf) | Agents | 22 |
| 21 | [AutoGen Paper](https://arxiv.org/abs/2308.08155) | Agents | 23 |
| 22 | [LangGraph Docs](https://langchain-ai.github.io/langgraph/) | Agents | 23 |
| 23 | [Guardplane](https://github.com/lhy0718/Guardplane) | Agents | 24 |
| 24 | [OpenClaw](https://github.com/openclaw/openclaw) | Agents | 26 |
| 25 | [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) | Agents | 26 |
| 26 | [Manus Architecture (CodeAct)](https://medium.com/@pankaj_pandey/inside-manus-the-architecture-that-replaced-tool-calls-with-executable-code-d89e1caea678) | Agents | 26 |
| 27 | [NVIDIA Agent Toolkit / NemoClaw](https://nvidianews.nvidia.com/news/ai-agents) | Agents | 26 |
| 28 | [Anthropic Agent Autonomy Research](https://www.anthropic.com/research/measuring-agent-autonomy) | Agents | 26 |

---

## Consolidation

After completing all blocks:

- [ ] Re-take all five self-assessments. Identify remaining gaps.
- [ ] Walk through one question from each domain end-to-end.
- [ ] Write up your key experiences: cardinality reduction, crash triage agent design, agentic framework architecture, closed-loop observability vision, security architecture decisions. Each as a concise narrative: context, approach, results.
- [ ] Review your crash triage agent's architecture doc. Be able to whiteboard it in 10 minutes.
- [ ] Build something: take your minimal framework from Block 25, wire it to real tools (OpenSearch, Prometheus), and run a real investigation.
