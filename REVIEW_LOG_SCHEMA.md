# Review Log Schema

## File: `review_log.csv`

Each row is one review event — a single timestamped measurement of your retention on a block.

## Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `date` | YYYY-MM-DD | When the review happened | `2026-03-20` |
| `block_id` | int (1-25) | Block number | `9` |
| `block_name` | string | Short name for readability | `Distributed Consensus` |
| `domain` | A-E | Which domain | `B` |
| `review_type` | enum | `initial`, `3day`, `10day`, `30day`, `adhoc`, `rollup` | `10day` |
| `days_since_completion` | int | Calendar days since you finished the block | `10` |
| `days_since_last_review` | int | Calendar days since your previous review of this block (0 for initial) | `7` |
| `time_spent_minutes` | int | How long the review took | `12` |
| `questions_attempted` | int | How many questions you tried to answer | `3` |
| `questions_recalled` | int | How many you answered correctly from memory | `2` |
| `confidence_before` | int (1-5) | Your confidence going IN to the review | `3` |
| `confidence_after` | int (1-5) | Your confidence AFTER the review | `4` |
| `gaps` | string | Free text: what you forgot or got wrong | `Forgot quorum math for 5-node cluster` |

## Example Rows

```csv
date,block_id,block_name,domain,review_type,days_since_completion,days_since_last_review,time_spent_minutes,questions_attempted,questions_recalled,confidence_before,confidence_after,gaps
2026-03-18,1,Data Model,A,initial,0,0,45,3,3,4,4,
2026-03-21,1,Data Model,A,3day,3,3,8,2,2,4,4,
2026-03-22,2,TSDB Engine,A,initial,0,0,60,3,2,3,3,Gorilla XOR encoding details fuzzy
2026-03-25,2,TSDB Engine,A,3day,3,3,10,2,1,3,2,Forgot WAL segment rotation trigger
2026-03-28,1,Data Model,A,10day,10,7,12,3,2,3,4,Histogram bucket interpolation math
2026-04-01,2,TSDB Engine,A,10day,10,7,15,3,2,2,3,Head block mmap transition still weak
2026-04-17,1,Data Model,A,30day,30,19,10,3,3,4,5,
```

## Review Types

| Type | When | What You Do |
|------|------|-------------|
| `initial` | Day you finish the block | Log time spent, attempt exercises, record baseline confidence |
| `3day` | 3 days after completion | 2 recall questions from memory, 5 min |
| `10day` | 10 days after completion | Teach-back or re-attempt Build from memory, 15 min |
| `30day` | 30 days after completion | Cold explanation, 10 min |
| `adhoc` | Any time you revisit | Unscheduled review (curiosity, need for work, etc.) |
| `rollup` | After all blocks in a domain | Full domain self-assessment |

## Analytics You Can Run Later

### 1. Retention Curve Per Block
Plot `confidence_after` vs `days_since_completion` for a single block.
Shows how your retention decays over time for that topic.

### 2. Recall Rate Over Time
`questions_recalled / questions_attempted` per review.
Aggregate by domain to see which domains you retain better.

### 3. Decay Rate Comparison
For each block, compute: `confidence_after(3day) - confidence_after(30day)`.
Blocks with the steepest drop = hardest to retain = need more review.

### 4. Domain Difficulty Ranking
Average `confidence_after` across all blocks in a domain at the 30-day mark.
Lower average = harder domain for you.

### 5. Time Investment vs Retention
Plot `time_spent_minutes` (cumulative per block) vs final `confidence_after`.
Shows which blocks gave you the most retention per hour invested.

### 6. Confidence Calibration
Compare `confidence_before` vs actual `questions_recalled / questions_attempted`.
If confidence_before is consistently higher than recall rate, you're overconfident.
If consistently lower, you're underconfident. Both are useful to know.

### 7. Review Effectiveness
`confidence_after - confidence_before` per review session.
Shows whether reviews are actually helping or just consuming time.

### 8. Learning Velocity
Track how long `initial` completion takes per block as you progress.
If later blocks take less time, you're building transferable mental models.

## Quick Load (Python)

```python
import pandas as pd

df = pd.read_csv('review_log.csv')
df['date'] = pd.to_datetime(df['date'])
df['recall_rate'] = df['questions_recalled'] / df['questions_attempted']
df['confidence_delta'] = df['confidence_after'] - df['confidence_before']
```
