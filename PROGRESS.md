# Progress

## Active Reviews

<!-- Run `python3 review_check.py` to see what's due. -->

| Block | Review Type | Due Date | Status |
|-------|------------|----------|--------|

## Tier 1 — Build Judgment (read, build, break, write)

Full review tracking: 3-day, 10-day, 30-day.

| # | Block | Tier | Completed | 3-day | 10-day | 30-day | Confidence | Write-Up |
|---|-------|------|-----------|-------|--------|--------|------------|----------|
| 21 | Reasoning Loop (ReAct) | 1 | | | | | | [ ] How Agent Loops Fail |
| 22 | Context Management & Memory | 1 | | | | | | [ ] Context Is the Bottleneck |
| 24 | Agent Security & Guardrails | 1 | | | | | | [ ] Agent Attack Surface |
| 11 | AI Observability (Four Layers) | 1 | | | | | | [ ] Monitoring My Agent in Production |

## Tier 2 — Know the Landscape (read + write the tradeoff)

Log initial completion only. Review = re-read your own write-up.

| # | Block | Tier | Completed | Confidence | Write-Up |
|---|-------|------|-----------|------------|----------|
| 23 | Multi-Agent Orchestration | 2 | | | [ ] When to Use Multiple Agents |
| 25 | Framework Synthesis | 2 | | | [ ] The Five Framework Layers |
| 26 | Autonomous Agent Platforms | 2 | | | [ ] Three Models for Agent Distribution |
| 12 | LLM Tracing (OTEL + LangFuse) | 2 | | | [ ] What to Trace in an LLM Call |
| 13 | Output Quality Eval (LLM-as-Judge) | 2 | | | [ ] How I'd Evaluate My Agent |
| 14 | Infrastructure Metrics for AI | 2 | | | [ ] Five Metrics for LLM Inference |
| 19 | Prompt Injection & AI Threat Model | 2 | | | [ ] Direct vs Indirect Injection |
| 9 | Distributed Consensus | 2 | | | [ ] Raft in One Page |
| 7 | LSM Trees vs B-Trees | 2 | | | [ ] LSM vs B-Tree in One Paragraph |

## Tier 3 — Know It Exists (skim, 3-sentence summary)

No tracking. Reference material.

| # | Block | 3-Sentence Summary Written |
|---|-------|---------------------------|
| 6 | PromQL Deep Dive | [ ] |
| 8 | Columnar vs Row-Oriented | [ ] |
| 10 | TSDB Design Patterns | [ ] |
| 15 | Tool Landscape | [ ] |
| 16 | eBPF Observability | [ ] |
| 17 | Profiling & SLOs | [ ] |
| 18 | Observability Pipelines | [ ] |
| 20 | Agent Security Architecture | [ ] |

## Deferred — Already Known / Revisit If Gaps Found

| # | Block | Reason |
|---|-------|--------|
| 1 | Data Model & Metric Types | Operational muscle memory |
| 2 | TSDB Storage Engine | Deep internal — revisit for storage debugging |
| 3 | On-Disk Index & Queries | Revisit for slow query debugging |
| 4 | Scraping & Remote Write | Revisit for WAL / data loss issues |
| 5 | Scaling (Thanos/Mimir) | Already done 30M→3M cardinality work |

## Learning Sequence

```
START HERE
    │
    ▼
Block 21: Reasoning Loop ──── build agent, break it, write "How Agent Loops Fail"
    │
    ▼
Block 22: Context Management ─ extend agent, find the context wall, write "Context Is the Bottleneck"
    │
    ▼
Block 24: Agent Security ───── red-team your own agent, write "Agent Attack Surface"
    │
    ▼
Block 11: AI Observability ─── define "healthy" for your agent, write "Monitoring My Agent"
    │
    ▼
Tier 2: One block per session, read + write the tradeoff page
    │
    ▼
Tier 3: Skim when a real problem demands it
```

## Write-Up Library

Store your write-ups here: `writeups/` directory. These are your artifacts — reusable in design reviews, team discussions, and future reference.

## How to Use

### Daily Workflow
1. Run `python3 review_check.py` — see what's due
2. Do due reviews (5-15 min): re-read your own write-up, test yourself
3. Work on next block
4. Log in `review_log.csv`

### Review Cadence (Tier 1 only)
- **3-day** — Re-read your write-up. Can you explain the tradeoff cold? (5 min)
- **10-day** — Without looking at your write-up, explain the topic to someone (or record yourself). Compare to your write-up after. (15 min)
- **30-day** — Can you still articulate the core tradeoff and failure modes? (10 min)

### Confidence Scale
| Score | Meaning |
|-------|---------|
| 5 | Can explain the tradeoff cold and apply it to a new problem I haven't seen |
| 4 | Can explain cold, might miss edge cases |
| 3 | Need a minute to recall, then solid |
| 2 | Remember the shape but not the details |
| 1 | Need to re-read |
