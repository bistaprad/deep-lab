# Day 10 — Tool Landscape and Decision Framework

## Decision Matrix

| Platform | Best For | Data Residency | Framework Lock-in | Cost |
|----------|----------|----------------|-------------------|------|
| **LangFuse** (OSS) | Full tracing, evals, prompt mgmt | Self-hosted | None | Free (self-hosted) |
| **LangSmith** | LangChain-native tracing | SaaS (LangChain) | LangChain | Per-trace |
| **Arize Phoenix** (OSS) | Embedding drift, ML+LLM unified | Self-hosted | None | Free |
| **Helicone** | Lightweight proxy logging, cost | SaaS | None | Per-request |
| **Braintrust** | Eval-first workflows | SaaS | None | Per-eval |
| **W&B Weave** | Research + prod unified | SaaS/self-hosted | W&B ecosystem | Per-trace |
| **Custom (Prom+OTEL)** | Full control, no data egress | Your infra | None | Eng time |

## When to Choose What

**Choose LangFuse when:**
- You need self-hosting (sensitive data, compliance)
- You're not married to LangChain
- You want eval + tracing + prompt management in one tool
- You have existing ClickHouse experience (bonus)

**Choose LangSmith when:**
- You're already using LangChain/LangGraph
- SaaS is acceptable (data can leave your cluster)
- You want zero-instrumentation tracing (auto-captured by LangChain)

**Choose Arize Phoenix when:**
- You have embedding-based retrieval (RAG with vector DB)
- You need embedding drift detection
- You want unified ML + LLM observability

**Choose custom Prometheus + OTEL when:**
- You have strict data residency requirements
- You already run Prometheus/Grafana
- You only need infrastructure + behavioral metrics (not full trace UI)

## Architecture for the Crash Triage Agent

```
                                    ┌─────────────┐
                                    │  Grafana     │
                                    │  Dashboards  │
                                    └──────┬───────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        │                  │                  │
                 ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
                 │ Prometheus   │   │  LangFuse    │   │  Alert      │
                 │ (infra +     │   │  (traces +   │   │  Manager    │
                 │  agent       │   │   evals +    │   │             │
                 │  metrics)    │   │   prompts)   │   │             │
                 └──────▲──────┘   └──────▲──────┘   └─────────────┘
                        │                  │
                        │                  │
                 ┌──────┴──────────────────┴──────┐
                 │       Crash Triage Agent        │
                 │                                 │
                 │  Prometheus client:              │
                 │   - tool_call_count              │
                 │   - investigation_duration       │
                 │   - context_utilization          │
                 │   - token_cost                   │
                 │                                 │
                 │  LangFuse SDK:                   │
                 │   - Full trace per investigation │
                 │   - Tool call spans              │
                 │   - LLM generations              │
                 │   - Eval scores                  │
                 └─────────────────────────────────┘
```

### Why This Stack

1. **Prometheus** — already deployed, zero new infrastructure. Handles Layer 1 (infra) and behavioral metrics (tool counts, durations).
2. **LangFuse** — self-hosted, data stays in cluster. Handles Layer 2 (tracing) and Layer 3 (evals).
3. **Grafana** — unified view. Prometheus data source for metrics, LangFuse API for quality trends.
4. **No new infrastructure** except a LangFuse deployment (Postgres + ClickHouse, both can run in existing K8s cluster).

### What Goes Where

| Signal | Tool | Why |
|--------|------|-----|
| API latency, error rate | Prometheus | Time-series, alerting |
| Token cost per investigation | Prometheus | Aggregate trends, alerts |
| Tool call count, duration | Prometheus | Real-time alerting |
| Full prompt/completion text | LangFuse | Debugging, replay |
| Tool call arguments/results | LangFuse | Root cause debugging |
| Eval scores per investigation | LangFuse | Quality tracking |
| Prompt version performance | LangFuse | A/B comparison |
| Model version tracking | Both | Regression detection |

## Exercises

1. Write the justification for each tool choice in your stack. Why not LangSmith? Why not pure custom?
2. Design the Grafana dashboard layout: which panels, what queries, how organized?
3. Write the LangFuse integration code: trace creation, span for each tool call, score attachment.

## Key Takeaways

> "The best observability stack reuses what you already have. Prometheus + Grafana handles infrastructure and behavioral metrics. LangFuse adds the AI-specific layer: traces, evals, prompt management. No new paradigms — just new signals."

> "Self-hosting LangFuse is the right call when your agent processes sensitive operational data. The tradeoff is operational overhead for a ClickHouse + Postgres deployment — manageable in an existing K8s cluster."

---

## Build — Unified Observability Integration

Build the full observability integration for your crash triage agent: Prometheus metrics + LangFuse traces + eval scoring in one codebase.

**Requirements:**
1. Agent wrapper that on every investigation:
   - Starts a LangFuse trace (or JSON trace if LangFuse not running)
   - Records Prometheus metrics (duration, tokens, tool calls, cost)
   - Runs LLM-as-judge eval and records score in trace
   - Logs model_version for regression detection
2. Prometheus `/metrics` endpoint
3. A simple CLI: `python run_agent.py --crash-ticket ticket.json` that runs an investigation with full instrumentation
4. Summary output: trace_id, duration, tokens, cost, eval_score, model_version

**Stretch:** Add model version change detection — if `model_version` differs from last run, log a warning and trigger an eval run.

**What you'll learn:** How all the observability layers fit together in one codebase. The Build artifacts from blocks 11-14 should compose into this.

---

## Design — Observability Platform for a Fleet of AI Agents

Design an observability platform that monitors 10+ AI agents across an organization.

**Requirements:**
- Each agent reports: traces (LangFuse), metrics (Prometheus), eval scores
- Central dashboard: per-agent health, cost, quality trend
- Cross-agent analytics: total token spend, cost allocation by team
- Alerting: per-agent eval regression, cost anomaly, tool failure rate
- Self-service: teams can onboard new agents and define their own eval datasets

**Design decisions:**
- Single LangFuse instance or per-team? How do you handle multi-tenancy?
- How do you normalize eval scores across agents with different rubrics?
- How do you implement cost allocation when agents share the same Claude API key?
- What's the Grafana dashboard hierarchy? (Fleet overview → per-agent → per-investigation)
