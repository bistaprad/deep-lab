# Day 8 — Output Quality Evaluation (LLM-as-Judge)

## The Core Problem

You cannot write a unit test for LLM output correctness. Output is natural language, variably correct, and context-dependent. A response can be partially right, directionally correct but imprecise, or confidently wrong.

Solution: **automated evaluation using other LLMs** (LLM-as-judge).

## LLM-as-Judge Pattern

A separate LLM evaluates the output of your agent.

**Inputs to the judge:**
1. The original input/context
2. The agent's output
3. An evaluation rubric
4. (Optional) A reference/ground-truth answer

**Output from the judge:**
- Scores on defined dimensions
- Reasoning for each score

### Example Rubric for Crash Triage

```
Given the crash context and the agent's root cause analysis:

Score 1-5 on each dimension:
- Accuracy: Does the root cause match the evidence in the logs/metrics?
- Completeness: Are all key signals (logs, metrics, events) addressed?
- Actionability: Is the recommended remediation specific and correct?
- Hallucination: Does the agent claim evidence not present in the data?

Return JSON:
{
  "accuracy": int,
  "completeness": int,
  "actionability": int,
  "hallucination_detected": bool,
  "reasoning": string
}
```

## Pitfalls of LLM-as-Judge

| Pitfall | Description | Mitigation |
|---------|-------------|------------|
| **Positivity bias** | Judges rate verbose, well-structured answers higher regardless of correctness | Rubric explicitly penalizes filler; test with known-wrong but well-written answers |
| **Self-preference** | Claude judges rate Claude outputs higher than GPT outputs (and vice versa) | Use a different model family for judging |
| **Length bias** | Longer answers get higher scores | Normalize for length in rubric; include brevity as a positive signal |
| **Position bias** | In A/B comparisons, judges prefer the first option | Randomize order; run both orderings |
| **Sycophancy** | Judge agrees with the framing of the question | Neutral framing in rubric; avoid leading questions |

### Calibration

Before trusting automated evals, calibrate against human labels:
1. Have humans score 50-100 examples
2. Run LLM-as-judge on the same examples
3. Compute correlation (Cohen's kappa or Spearman)
4. If correlation > 0.7: judge is usable
5. If correlation < 0.5: revise rubric or change judge model

## Reference-Based Eval

When you have ground truth (known-correct RCA), you can do more precise evaluation.

### Semantic Similarity

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
agent_embedding = model.encode(agent_rca)
reference_embedding = model.encode(ground_truth_rca)
similarity = cosine_similarity(agent_embedding, reference_embedding)
# Threshold: > 0.85 = pass
```

### Field-Level Matching (More Precise)

```python
scores = {
    "crash_category_correct": agent.category == reference.category,  # exact match
    "evidence_contains_key_log": key_log_line in agent.evidence,     # substring
    "action_matches": fuzzy_match(agent.action, reference.action),   # fuzzy
}
```

## Evals in CI

Every PR that changes system prompt or tool definitions must run the eval suite.

**Eval suite structure:**
- 30+ ground truth cases covering different crash categories
- Each case: input context + expected RCA + scoring rubric
- Gate: eval pass rate must not drop more than 5% from baseline
- Run time: ~5 minutes for 30 cases (parallelized, ~10s per case)

**Implementation:**
```
pytest test_evals.py
  → Load ground truth dataset from LangFuse
  → Run agent on each case
  → Score with LLM-as-judge
  → Assert aggregate pass rate >= threshold
  → Store results back in LangFuse for trend tracking
```

This prevents prompt regressions — the most common failure when iterating quickly on prompts.

## Inter-Rater Reliability

To measure judge consistency:
1. Run the same judge on the same 5 cases twice (different API calls)
2. Compare scores between runs
3. Compute variance per dimension
4. High variance (>1 point on 5-point scale) = rubric is ambiguous, needs refinement

## Exercises

1. Write an LLM-as-judge rubric for 5 crash triage test cases. Run it. Examine where the judge disagrees with your own assessment.
2. Take a known-correct RCA and deliberately introduce a hallucinated log line. Does your judge catch it? If not, how do you improve the rubric?
3. Run the judge twice on the same case. Is the score stable? What does variance tell you about rubric quality?

## Key Takeaways

> "LLM-as-judge is the practical solution for automated quality evaluation, but it requires calibration against human labels and awareness of systematic biases (positivity, self-preference, length)."

> "Evals in CI are the quality gate for prompt engineering. Without them, every prompt change is a potential regression you won't discover until production."

---

## Build — Eval Harness with LLM-as-Judge

Build a complete evaluation framework for your crash triage agent.

**Requirements:**
1. **Dataset**: store 10+ test cases as JSON: `{input_context, expected_rca, crash_category}`
2. **Runner**: for each test case, call the agent and capture the output
3. **Judge**: send (input, output, expected, rubric) to Claude as judge. Parse structured scores.
4. **Rubric**: score on accuracy (1-5), completeness (1-5), hallucination_detected (bool)
5. **Reporter**: compute aggregate pass rate, per-dimension averages, print failures
6. **CI gate**: exit code 1 if pass rate < threshold (configurable)
7. **Variance check**: run judge twice on same cases, report score stability

**Stretch:** Store results over time (JSON or SQLite). Plot eval score trend.

**What you'll learn:** The full eval loop from dataset to CI gate, how to calibrate a judge, what score variance tells you about rubric quality.

---

## Design — Eval Platform for Multi-Agent Systems

Design an evaluation platform that supports multiple agents, prompt versions, and model versions.

**Requirements:**
- Register agents (crash triage, code review, customer support) each with their own test datasets
- Run evals on-demand or triggered by: prompt change, model version change, schedule
- Compare results across prompt versions (A/B testing for prompts)
- Store historical results for trend analysis
- Alert when eval pass rate drops below threshold for any agent

**Design decisions:**
- How do you version prompts and link eval results to specific prompt versions?
- How do you handle eval cost? (Running 100 test cases with Claude-as-judge costs ~$5)
- How do you parallelize eval runs without hitting API rate limits?
- How do you handle flaky evals (LLM judge gives different scores on same input)?
