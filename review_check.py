#!/usr/bin/env python3
"""
Run this when you start a study session:
    python3 review_check.py

Reads review_log.csv, calculates what reviews are due today,
and prints your study agenda.
"""

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

REVIEW_SCHEDULE = [
    (3, "3day", "Quick recall: 2 questions from memory (5 min)"),
    (10, "10day", "Application: teach the concept or redo a Build exercise (15 min)"),
    (30, "30day", "Cold check: explain the core idea with no warmup (10 min)"),
]

SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / "review_log.csv"

BLOCKS = {
    1: ("Data Model & Metric Types", "A"),
    2: ("TSDB Storage Engine", "A"),
    3: ("On-Disk Index & Query Execution", "A"),
    4: ("Scraping, Remote Write, Staleness", "A"),
    5: ("Horizontal Scaling (Thanos/Mimir)", "A"),
    6: ("PromQL Deep Dive", "A"),
    7: ("LSM Trees vs B-Trees", "B"),
    8: ("Columnar vs Row-Oriented Storage", "B"),
    9: ("Distributed Consensus", "B"),
    10: ("TSDB Design Patterns", "B"),
    11: ("AI Observability Intro", "C"),
    12: ("LLM Tracing (OTEL + LangFuse)", "C"),
    13: ("Output Quality Eval (LLM-as-Judge)", "C"),
    14: ("Infrastructure Metrics for AI", "C"),
    15: ("Tool Landscape Decision Framework", "C"),
    16: ("eBPF & Kernel-Level Observability", "D"),
    17: ("Continuous Profiling & SLO Alerting", "D"),
    18: ("Observability Pipelines & Closed-Loop", "D"),
    19: ("AI Threat Model & Prompt Injection", "D"),
    20: ("Agent Security Architecture", "D"),
    21: ("Reasoning Loop (ReAct)", "E"),
    22: ("Context Management & Memory", "E"),
    23: ("Multi-Agent Orchestration", "E"),
    24: ("Agent Security & Guardrails", "E"),
    25: ("Framework Synthesis", "E"),
    26: ("Autonomous Agent Platforms", "E"),
}


def load_reviews():
    """Load all review events from the CSV log."""
    if not LOG_FILE.exists():
        return []
    rows = []
    with open(LOG_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("date"):
                continue
            row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
            row["block_id"] = int(row["block_id"])
            rows.append(row)
    return rows


def get_completion_dates(reviews):
    """Find the initial completion date for each block."""
    completions = {}
    for r in reviews:
        if r["review_type"] == "initial":
            completions[r["block_id"]] = r["date"]
    return completions


def get_completed_reviews(reviews):
    """For each block, collect which review types have been done."""
    done = defaultdict(set)
    for r in reviews:
        done[r["block_id"]].add(r["review_type"])
    return done


def main():
    today = datetime.now().date()
    reviews = load_reviews()

    if not reviews:
        print("=" * 60)
        print("  No reviews logged yet.")
        print()
        print("  Start by completing a block, then log it:")
        print()
        print("  Append a row to review_log.csv with review_type=initial")
        print("  (see REVIEW_LOG_SCHEMA.md for the full column list)")
        print("=" * 60)
        sys.exit(0)

    completions = get_completion_dates(reviews)
    done = get_completed_reviews(reviews)

    due_today = []
    upcoming = []

    for block_id, completion_date in sorted(completions.items()):
        block_name, domain = BLOCKS[block_id]
        for days, review_type, description in REVIEW_SCHEDULE:
            if review_type in done[block_id]:
                continue
            due_date = completion_date + timedelta(days=days)
            entry = {
                "block_id": block_id,
                "block_name": block_name,
                "domain": domain,
                "review_type": review_type,
                "due_date": due_date,
                "description": description,
                "days_overdue": (today - due_date).days,
            }
            if due_date <= today:
                due_today.append(entry)
            elif due_date <= today + timedelta(days=3):
                upcoming.append(entry)

    print()
    print("=" * 60)
    print(f"  STUDY AGENDA — {today.strftime('%A, %B %d, %Y')}")
    print("=" * 60)

    if due_today:
        print()
        print("  DUE NOW:")
        print()
        for e in sorted(due_today, key=lambda x: x["days_overdue"], reverse=True):
            overdue = ""
            if e["days_overdue"] > 0:
                overdue = f"  [!] {e['days_overdue']}d overdue"
            print(f"  [{e['review_type']:>5}]  Block {e['block_id']:>2} — {e['block_name']}")
            print(f"          {e['description']}{overdue}")
            print()
    else:
        print()
        print("  Nothing due today. Work on new blocks or take a break.")
        print()

    if upcoming:
        print("  COMING UP (next 3 days):")
        print()
        for e in sorted(upcoming, key=lambda x: x["due_date"]):
            print(f"  [{e['review_type']:>5}]  Block {e['block_id']:>2} — {e['block_name']}  (due {e['due_date'].strftime('%b %d')})")
        print()

    completed_count = len(completions)
    total_reviews_done = sum(
        1 for bid in completions
        for _, rt, _ in REVIEW_SCHEDULE
        if rt in done[bid]
    )
    total_reviews_possible = completed_count * len(REVIEW_SCHEDULE)

    print("-" * 60)
    print(f"  Blocks completed: {completed_count}/25")
    if total_reviews_possible > 0:
        print(f"  Reviews completed: {total_reviews_done}/{total_reviews_possible}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
