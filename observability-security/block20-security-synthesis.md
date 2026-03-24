# Block 20 — Agent Security Architecture (PREVENT / DETECT / RESPOND)

## The Framework: PREVENT → DETECT → RESPOND

Every security control maps to one of these layers. A mature posture has depth at all three.

### Layer 1 — PREVENT

Stop attacks before they cause harm.

| Control | What It Does | Implementation |
|---------|-------------|----------------|
| **Structural prompt separation** | Delimit trusted instructions from untrusted data | XML tags in system prompt, explicit boundary language |
| **Least privilege tools** | Minimize what the agent can do | Read-only tools, hard-scoped inputs |
| **Network policy** | Limit agent's network reach | K8s NetworkPolicy, allowlist only |
| **RBAC** | Limit K8s API access | Dedicated service account, minimal permissions |
| **Secret management** | Protect API keys | Vault/KMS, rotation, never in git |
| **Data redaction at ingestion** | Agent never sees secrets in logs | Alloy/Fluentd regex scrubbing |
| **Input validation** | Reject out-of-scope tool calls | Validate cluster/app/time_range against ticket |
| **SDK pinning** | Prevent supply chain attacks | Lockfiles, review diffs on upgrade |

### Layer 2 — DETECT

Identify attacks and anomalies in real-time.

| Control | What It Detects | Implementation |
|---------|----------------|----------------|
| **Injection pattern detection** | Known injection strings in tool results | Regex scanner on all tool results |
| **Output anomaly detection** | Agent output contains secrets/PII/system prompt | Regex + heuristic scanner on output |
| **Behavioral monitoring** | Unusual tool call patterns | Prometheus alerts: tool_call_count > 15, context_util > 85% |
| **Eval regression** | Quality drop after model version change | Auto-run eval suite on model_version change |
| **Cost anomaly** | Token consumption spike | Prometheus alert: cost > 2× rolling average |
| **Audit logging** | Full record of every tool call and response | LangFuse traces + structured logs |
| **Confidence calibration** | Agent overconfident on wrong answers | Track confidence_score vs eval_accuracy correlation |

### Layer 3 — RESPOND

Act on detected threats.

| Control | What It Does | Trigger |
|---------|-------------|---------|
| **Output blocking** | Prevent suspicious RCA from reaching Jira | Output scanner detects secrets/injection artifacts |
| **Human review queue** | Flag investigations for manual review | Low confidence score, high tool_call_count, detected anomaly |
| **Circuit breaker** | Stop agent from running more investigations | Sustained high error rate or detected attack |
| **Incident runbook** | Structured response to injection/exfiltration | Alert from detection layer |
| **Eval suite expansion** | Add new test cases from detected failures | Post-incident analysis |
| **Pattern update** | Update injection detection patterns | New attack pattern identified |

## The Security Document

### Template: "AI Agent Security Posture"

**1. System Description**
- What the agent does
- What data it accesses (classification)
- What tools it has (permissions)

**2. Threat Model**
- Attack vectors: indirect prompt injection, data exfiltration, tool manipulation
- Threat actors: internal (accidental log injection), external (deliberate)
- Assets at risk: operational data, system topology, API keys

**3. Prevention Controls**
- Structural separation in prompts
- Least privilege tool design
- Network and RBAC restrictions
- Data redaction pipeline

**4. Detection Controls**
- Injection pattern scanner
- Output anomaly detection
- Behavioral metrics + alerts
- Eval regression monitoring

**5. Response Procedures**
- Output blocking criteria
- Human review escalation
- Circuit breaker conditions
- Incident response steps

**6. Gaps and Roadmap**
- Known limitations of current defenses
- Planned improvements with timeline

## Connecting Security to Your Agent Design

Your `requires_human_review` flag is a **security control** as much as a quality control:
- Low confidence → human reviews → catches manipulated output

Your `investigation_steps` audit trail is a **security forensics capability**:
- If injection occurs, you can trace exactly which tool returned the malicious data

Your eval harness is a **regression detection system**:
- Model version changes caught before they reach production

The strongest approach connects security to actual system design rather than treating it as abstract theory.

## Self-Assessment Questions

Answer out loud, no notes:

1. How would you detect if your agent was being manipulated via indirect prompt injection?
2. Walk through the security architecture of your crash triage agent.
3. What happens when Anthropic updates the Claude model version?
4. How does your agent prevent data exfiltration?
5. What is your incident response plan if prompt injection is detected?

## Key Takeaways

> "Security for AI agents isn't a separate concern — it's woven into the system design. The human review flag is a security control. The audit trail is forensic capability. The eval suite is regression detection."

> "PREVENT stops known attacks. DETECT catches novel attacks. RESPOND limits damage and improves defenses. You need all three layers — any single layer alone has gaps."

---

## Build — Security Test Suite for AI Agents

Build an automated security test suite that probes your agent for vulnerabilities.

**Requirements:**
1. **Injection test cases** (10+): craft payloads embedded in simulated tool results (OpenSearch logs, Prometheus output). Each tries to:
   - Extract the system prompt
   - Change the agent's behavior (produce a different output format)
   - Exfiltrate data (include internal IPs in output)
2. **Test runner**: for each test case, feed the payload as a tool result, capture agent output
3. **Assertions**: verify the agent did NOT follow the injected instructions:
   - Output does not contain system prompt text
   - Output follows the expected RCA format
   - Output does not contain planted canary strings
4. **RBAC validator**: given a K8s service account YAML, verify it has minimum permissions (no exec, no secrets access, no cluster-admin)
5. **NetworkPolicy validator**: given a NetworkPolicy YAML, verify it only allows egress to expected endpoints
6. **Report**: pass/fail per test, overall security posture score

**What you'll learn:** How to systematically test agent security, how to measure defense effectiveness, how RBAC and NetworkPolicy are validated.

---

## Design — AI Agent Incident Response System

Design the full incident response pipeline for when an AI agent security event is detected.

**Requirements:**
- Detection: injection detected in tool results OR suspicious output content OR eval score anomaly
- Automated response: block the suspicious output, quarantine the investigation, alert security team
- Investigation: audit log provides full replay of what happened (tool calls, results, agent reasoning)
- Remediation: update injection detection patterns, add test case to security suite, update system prompt defenses
- Post-incident: generate report with timeline, root cause, impact assessment, remediation steps

**Design decisions:**
- How fast does the response need to be? (Can you afford async analysis, or must you block in real-time?)
- How do you distinguish a security event from a quality issue? (Low eval score could be either)
- How do you handle the case where the agent is compromised but continues to produce plausible-looking output?
- How do you test the incident response pipeline itself? (Game days, red team exercises)
