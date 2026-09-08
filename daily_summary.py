#!/usr/bin/env python3
"""
Auto Job Applier — Daily Summary Reporter

Reads all applied_history.csv, question_jobs.csv, sleep_jobs.csv, and
resume_recommendations.csv across LinkedIn and Wellfound bots, and prints
a combined daily summary.

Usage:
    python3 daily_summary.py              # today's stats
    python3 daily_summary.py --all        # all-time stats
    python3 daily_summary.py --date 2026-09-08  # specific date
"""

import argparse
import csv
import os
import sys
from collections import Counter
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# CSV files to scan
PLATFORMS = {
    "LinkedIn": os.path.join(ROOT, "linkedin_autoapply", "linkedin_bot"),
    "Wellfound": os.path.join(ROOT, "wellfound_autoapply", "wellfound_bot"),
    "Naukri": os.path.join(ROOT, "naukri_autoapply", "naukri_bot"),
    "Internshala": os.path.join(ROOT, "internshala_autoapply", "internshala_bot"),
}


def read_csv_rows(path: str, date_filter: str = None) -> list[dict]:
    """Read a CSV file, optionally filtering by date prefix in the timestamp column."""
    if not os.path.exists(path):
        return []
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if date_filter:
                    ts = row.get("timestamp", "")
                    if not ts.startswith(date_filter):
                        continue
                rows.append(row)
    except Exception:
        pass
    return rows


def count_by_status(rows: list[dict]) -> Counter:
    """Count rows by their 'status' column."""
    return Counter(row.get("status", "unknown") for row in rows)


def generate_summary(date_filter: str = None, show_all: bool = False):
    """Generate and print the daily summary."""
    if show_all:
        date_filter = None
        date_label = "All Time"
    elif date_filter is None:
        date_filter = datetime.now().strftime("%Y-%m-%d")
        date_label = f"Today ({date_filter})"
    else:
        date_label = date_filter

    print()
    print("╔" + "═" * 68 + "╗")
    print(f"║  📊 AUTO JOB APPLIER — DAILY SUMMARY" + " " * 31 + "║")
    print(f"║  📅 {date_label:<63}║")
    print("╠" + "═" * 68 + "╣")

    total_applied = 0
    total_skipped = 0
    total_failed = 0
    total_questions = 0
    total_sleep = 0

    for platform, bot_dir in PLATFORMS.items():
        history_path = os.path.join(bot_dir, "applied_history.csv")
        rows = read_csv_rows(history_path, date_filter)

        if not rows:
            continue

        statuses = count_by_status(rows)
        applied = sum(v for k, v in statuses.items() if k.startswith("applied"))
        skipped = sum(v for k, v in statuses.items() if k.startswith("skipped"))
        failed = sum(v for k, v in statuses.items()
                     if k.startswith("failed") or k.startswith("error"))
        uncertain = sum(v for k, v in statuses.items() if k.startswith("uncertain"))

        total_applied += applied
        total_skipped += skipped
        total_failed += failed

        print(f"║                                                                    ║")
        print(f"║  🔹 {platform:<63}║")
        print(f"║     ✅ Applied: {applied:<5}  ⏭️  Skipped: {skipped:<5}  ❌ Failed: {failed:<5}   ║")
        if uncertain:
            print(f"║     ❓ Uncertain: {uncertain:<50}║")

        # Question jobs
        q_path = os.path.join(bot_dir, "question_jobs.csv")
        q_rows = read_csv_rows(q_path, date_filter)
        if q_rows:
            total_questions += len(q_rows)
            print(f"║     📋 Jobs needing manual answers: {len(q_rows):<28}║")

        # Sleep jobs (Wellfound)
        s_path = os.path.join(bot_dir, "sleep_jobs.csv")
        s_rows = read_csv_rows(s_path, date_filter)
        if s_rows:
            total_sleep += len(s_rows)
            print(f"║     😴 Jobs parked (sleep mode): {len(s_rows):<31}║")

    # Resume recommendations (LinkedIn only)
    rec_path = os.path.join(ROOT, "linkedin_autoapply", "linkedin_bot",
                            "resume_recommendations.csv")
    rec_rows = read_csv_rows(rec_path, date_filter)
    if rec_rows:
        categories = Counter(row.get("recommended_resume", "Unknown") for row in rec_rows)
        print(f"║                                                                    ║")
        print(f"║  📄 Resume Recommendations (LinkedIn)                              ║")
        for cat, count in categories.most_common():
            bar = "█" * min(count, 30)
            print(f"║     {cat:<25} {count:>3}  {bar:<34}║")

    print(f"║                                                                    ║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  🎯 TOTALS                                                         ║")
    print(f"║     ✅ Applied:     {total_applied:<48}║")
    print(f"║     ⏭️  Skipped:     {total_skipped:<48}║")
    print(f"║     ❌ Failed:      {total_failed:<48}║")
    if total_questions:
        print(f"║     📋 Need answers: {total_questions:<47}║")
    if total_sleep:
        print(f"║     😴 Parked:       {total_sleep:<47}║")
    print("╠" + "═" * 68 + "╣")

    # Goal tracking
    goal = 100
    pct = min(100, int(total_applied / goal * 100)) if goal else 0
    bar_filled = pct // 2
    bar = "█" * bar_filled + "░" * (50 - bar_filled)
    print(f"║  🎯 Daily Goal: {total_applied}/{goal} applications                             ║")
    print(f"║     [{bar}] {pct}%  ║")

    if total_applied >= goal:
        print(f"║     🎉 GOAL REACHED! Great job today!                              ║")
    elif total_applied >= goal * 0.7:
        print(f"║     💪 Almost there! Run one more session to hit {goal}.              ║")
    else:
        remaining = goal - total_applied
        print(f"║     📈 {remaining} more to go. Keep pushing!                            ║")

    print("╚" + "═" * 68 + "╝")
    print()

    # Actionable next steps
    if total_questions > 0:
        print("📋 ACTION: Review question_jobs.csv files and answer manually:")
        for platform, bot_dir in PLATFORMS.items():
            q_path = os.path.join(bot_dir, "question_jobs.csv")
            if os.path.exists(q_path):
                print(f"   → {q_path}")

    if total_sleep > 0:
        print("😴 ACTION: Review sleep_jobs.csv files:")
        for platform, bot_dir in PLATFORMS.items():
            s_path = os.path.join(bot_dir, "sleep_jobs.csv")
            if os.path.exists(s_path):
                print(f"   → {s_path}")


def main():
    ap = argparse.ArgumentParser(description="Daily application summary")
    ap.add_argument("--all", action="store_true", help="Show all-time stats")
    ap.add_argument("--date", default=None, help="Filter by date (YYYY-MM-DD)")
    args = ap.parse_args()

    generate_summary(date_filter=args.date, show_all=args.all)


if __name__ == "__main__":
    main()
