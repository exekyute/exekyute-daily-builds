"""Command-line wrapper for the SOW tracker.

Reads a milestones file and an effort log, validates both, and writes two files:

  timeline.csv          - one row per week with cost to date, earned value, CPI,
                          the estimate at completion, the variance, the holdback,
                          and the status. The browser view in 02 reads this file.
  milestone_summary.csv - one row per milestone with its budget, actual cost, and
                          variance.

Usage:
  python cli.py
  python cli.py --milestones milestones.csv --effort effort_log.csv --holdback 0.10
"""

import argparse
import csv
import sys

from sow import build_timeline, milestone_summary
from validation import (
    ValidationError,
    validate_effort_row,
    validate_holdback_rate,
    validate_milestone_row,
)

TIMELINE_COLUMNS = [
    "week", "cost_to_date", "earned_value", "percent_complete", "percent_spent",
    "cpi", "eac", "vac", "holdback_accrued", "holdback_released", "status",
]
SUMMARY_COLUMNS = [
    "milestone_id", "name", "budget", "actual_cost", "variance", "percent_spent", "status",
]


def load_milestones(path):
    rows = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = validate_milestone_row(raw)
            if row["milestone_id"] in seen:
                raise ValidationError("Milestones: milestone_id %r appears twice" % row["milestone_id"])
            seen.add(row["milestone_id"])
            rows.append(row)
    if not rows:
        raise ValidationError("Milestones file is empty")
    return rows


def load_effort(path, known_milestones):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append(validate_effort_row(raw, known_milestones))
    if not rows:
        raise ValidationError("Effort log is empty")
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: str(row[col]) for col in columns})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vendor statement-of-work earned-value tracker.")
    parser.add_argument("--milestones", default="milestones.csv")
    parser.add_argument("--effort", default="effort_log.csv")
    parser.add_argument("--holdback", default="0.10", help="holdback rate, a share between 0 and 1")
    parser.add_argument("--timeline-out", default="timeline.csv")
    parser.add_argument("--summary-out", default="milestone_summary.csv")
    args = parser.parse_args(argv)

    try:
        holdback_rate = validate_holdback_rate(args.holdback)
        milestones = load_milestones(args.milestones)
        effort = load_effort(args.effort, {m["milestone_id"] for m in milestones})
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    timeline = build_timeline(milestones, effort, holdback_rate)
    summary = milestone_summary(milestones, effort)
    write_csv(args.timeline_out, TIMELINE_COLUMNS, timeline["rows"])
    write_csv(args.summary_out, SUMMARY_COLUMNS, summary)

    final = timeline["rows"][-1]
    print("Vendor SOW earned-value tracker")
    print("Total budget: %s   Holdback rate: %s" % (timeline["total_budget"], holdback_rate))
    print()
    header = "  %-5s %12s %12s %8s %12s %12s  %-11s" % (
        "Week", "Cost", "Earned", "CPI", "EAC", "VAC", "Status")
    print(header)
    for r in timeline["rows"]:
        print("  %-5d %12s %12s %8s %12s %12s  %-11s" % (
            r["week"], r["cost_to_date"], r["earned_value"], r["cpi"],
            r["eac"], r["vac"], r["status"]))
    print()
    print("At completion: EAC %s, variance %s, holdback released %s" % (
        final["eac"], final["vac"], final["holdback_released"]))
    print("Wrote %s and %s" % (args.timeline_out, args.summary_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
