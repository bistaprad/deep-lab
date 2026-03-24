# Block 16 — eBPF & Kernel-Level Observability

## What eBPF Is

**Extended Berkeley Packet Filter** — a technology that lets you run sandboxed programs in the Linux kernel without modifying kernel source code or loading kernel modules.

Originally designed for packet filtering (tcpdump). Now a general-purpose in-kernel execution engine used for: networking, security, tracing, and observability.

## Why eBPF Matters for Observability

Traditional instrumentation requires:
1. Adding SDK/library to application code
2. Redeploying the application
3. Per-language implementation (Go SDK, Java agent, Python library)
4. Application developer cooperation

eBPF-based instrumentation requires:
1. Deploy an agent to each node (DaemonSet in K8s)
2. That's it. No code changes. No redeployment. Language-agnostic.

This is the biggest shift in telemetry collection in the last decade.

## How eBPF Works

```
Kernel event (syscall, network packet, function entry)
     ↓
eBPF program triggers (attached to hook point)
     ↓
eBPF bytecode executes in kernel (verified at load time for safety)
     ↓
Results written to eBPF maps (shared memory between kernel and user-space)
     ↓
User-space agent reads maps, exports as Prometheus metrics / OTEL spans
```

### Safety Model

eBPF programs are verified before execution:
- No unbounded loops (guaranteed termination)
- No invalid memory access
- No unsafe kernel modifications
- Stack size limited (512 bytes)

This is what makes eBPF safe to run in production — the verifier guarantees it won't crash the kernel.

### Hook Points

| Hook Point | What It Captures | Example Use |
|-----------|-----------------|-------------|
| **kprobes / kretprobes** | Any kernel function entry/exit | Syscall tracing, file I/O |
| **uprobes / uretprobes** | Any user-space function entry/exit | Application function tracing |
| **tracepoints** | Predefined kernel events | Scheduler events, block I/O |
| **XDP (eXpress Data Path)** | Network packets before kernel stack | Packet filtering, DDoS mitigation |
| **TC (Traffic Control)** | Network packets at TC layer | Network policy enforcement |
| **socket filters** | Socket-level events | Connection tracking |

## eBPF Observability Tools

### Cilium Hubble (Network Observability)

```
Pod A → [eBPF captures packet at TC hook] → Pod B
            ↓
    Hubble flow log:
      src: pod-a (namespace: default)
      dst: pod-b (namespace: backend)
      protocol: HTTP
      method: GET
      path: /api/v1/users
      status: 200
      latency: 45ms
```

- Captures L3/L4/L7 network flows without sidecars
- Kubernetes-aware: resolves pod names, namespaces, services
- No application code changes
- Exports to Prometheus, OTEL, or Hubble UI
- Replaces: service meshes for observability-only use cases (Istio/Envoy sidecar overhead)

### Pixie (Application Observability)

- Auto-instruments HTTP, gRPC, MySQL, PostgreSQL, Redis, Kafka, DNS
- Captures request/response pairs with latency, status, body (configurable)
- No code changes, no sidecars, no language-specific agents
- Runs eBPF programs that attach to syscalls (read/write on sockets)
- Data stays in-cluster (edge compute model)
- PxL query language for ad-hoc analysis

### Tetragon (Security Observability)

- Cilium's security-focused eBPF tool
- Monitors: process execution, file access, network connections, privilege escalation
- Real-time policy enforcement in kernel (not just detection)
- Use case: detect and block unauthorized process execution in pods

### Grafana Beyla (Auto-Instrumentation)

- eBPF-based auto-instrumentation for HTTP/gRPC
- Produces OTEL traces and Prometheus metrics
- No code changes, no SDK, no language dependency
- Lightweight alternative to full Pixie/Hubble when you just need RED metrics

## eBPF vs Traditional Instrumentation

| | Traditional (SDK) | eBPF-Based |
|---|---|---|
| **Code changes** | Required | None |
| **Language support** | Per-language SDK | Language-agnostic (kernel-level) |
| **Deployment** | Per-application | Per-node (DaemonSet) |
| **Depth of data** | Deep (custom metrics, business logic) | Broad (syscall/network level) |
| **Overhead** | Varies (SDK quality) | Low (kernel-native, verified) |
| **Maintenance** | Update SDK in every app | Update DaemonSet |
| **Coverage** | Only instrumented apps | All processes on the node |
| **Custom metrics** | Yes (arbitrary business metrics) | No (limited to what kernel events expose) |

**Key insight:** eBPF doesn't replace SDK instrumentation — it complements it. Use eBPF for universal baseline coverage (network flows, request latency, error rates). Use SDKs for application-specific metrics (business logic, custom dimensions).

## Exercises

1. Draw the eBPF data flow: kernel event → eBPF program → map → user-space agent → Prometheus/OTEL. Label where the verifier runs and why it matters.
2. Compare traditional sidecar-based service mesh observability (Istio/Envoy) with eBPF-based (Cilium Hubble). What's the resource overhead difference?
3. You need HTTP request/response tracing for a polyglot microservice environment (Go, Java, Python, Node.js). Compare: instrument each with OTEL SDK vs deploy Pixie/Beyla. Tradeoffs?

## Key Takeaways

> "eBPF lets you observe everything on a node — network flows, syscalls, function calls — without touching application code. This changes the economics of instrumentation: instead of convincing every team to add an SDK, you deploy one DaemonSet."

> "eBPF is for breadth, SDKs are for depth. Use eBPF to get baseline RED metrics across all services automatically. Use SDKs to add business-specific dimensions to the services that matter most."

---

## Build — BCC/bpftrace Network Latency Tracer

Write a simple eBPF program (using BCC Python or bpftrace) that measures TCP connection latency.

**Requirements:**
1. Attach to `tcp_v4_connect` kprobe (connection initiation) and `tcp_v4_connect` kretprobe (connection established)
2. Measure time between connect and established → TCP handshake latency
3. Output: `{timestamp, src_ip, src_port, dst_ip, dst_port, latency_us}`
4. Aggregate into a histogram: latency distribution across all connections
5. Export as Prometheus metrics: `tcp_connect_latency_seconds_bucket{le="0.001"} 500`

**If running on Linux:** Use BCC Python (`from bcc import BPF`) or bpftrace one-liner.
**If not on Linux:** Implement a simulation: hook into Python socket library, measure connect() latency, export as Prometheus metrics. Same concept, different mechanism.

**What you'll learn:** How eBPF hooks into kernel functions, how kernel-level measurement works, the eBPF → map → user-space export pattern.

---

## Design — Zero-Instrumentation Service Mesh Observability

Design a system that provides full L7 observability (HTTP method, path, status, latency per request) across a microservice cluster without any application code changes or sidecar proxies.

**Requirements:**
- eBPF agents on each node capture HTTP request/response pairs
- Resolve source/destination to Kubernetes pod names and services
- Export as: Prometheus metrics (RED per service pair) and OTEL traces (distributed trace reconstruction)
- Dashboard: service dependency graph with latency/error rate on each edge

**Design decisions:**
- How do you reconstruct distributed traces from per-node eBPF data? (Correlate by TCP connection + timing?)
- How do you handle encrypted traffic (TLS)? (Attach to OpenSSL uprobes? Or only capture pre-encryption?)
- How do you handle HTTP/2 multiplexing? (Multiple requests on one TCP connection)
- What's the performance overhead budget? (Target: < 2% CPU per node)
