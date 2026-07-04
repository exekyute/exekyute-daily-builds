"""Command-line wrapper for the grant compliance engine.

Reads an award budget, a transaction list, and a reporting schedule, validates all
three, and writes three files:

  timeline.csv         - one row per period with the cumulative allowable drawdown,
                         the disallowed total, the burn rate, the runway, the
                         projection at award end, and the overdue report count. The
                         browser view in 02 reads this file.
  category_summary.csv - one row per budget category with its spend and remaining.
  deadlines.csv        - one row per report with its status as of the current period.

Usage:
  python cli.py
  python cli.py --award award.csv --transactions transactions.csv --schedule reporting_schedule.csv --months 12
"""

import argparse
import csv
import sys

from grant import build_timeline, category_summary, deadline_status, money, runway_periods
from validation import (
    ValidationError,
    validate_award_row,
    validate_deadline_row,
    validate_txn_row,
)
from decimal import Decimal

TIMELINE_COLUMNS = [
    "period", "cumulative_allowable", "cumulative_disallowed", "burn_rate",
    "remaining", "projected_total", "projected_variance", "status", "reports_overdue",
]
CATEGORY_COLUMNS = ["category", "budget", "spent", "remaining", "status"]
DEADLINE_COLUMNS = ["report", "due_period", "submitted", "status"]


def load_award(path):
    budgets = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            category, budget = validate_award_row(raw)
            if category in budgets:
                raise ValidationError("Award: category %r appears more than once" % category)
            budgets[category] = budget
    if not budgets:
        raise ValidationError("Award file is empty")
    return budgets


def load_transactions(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append(validate_txn_row(raw))
    if not rows:
        raise ValidationError("Transactions file is empty")
    return rows


def load_deadlines(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append(validate_deadline_row(raw))
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: str(row[col]) for col in columns})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grant drawdown and compliance engine.")
    parser.add_argument("--award", default="award.csv")
    parser.add_argument("--transactions", default="transactions.csv")
    parser.add_argument("--schedule", default="reporting_schedule.csv")
    parser.add_argument("--months", default="12", type=int, help="award period length in periods")
    parser.add_argument("--asof", default=None, type=int, help="current period, defaults to the latest transaction")
    parser.add_argument("--timeline-out", default="timeline.csv")
    parser.add_argument("--category-out", default="category_summary.csv")
    parser.add_argument("--deadlines-out", default="deadlines.csv")
    args = parser.parse_args(argv)

    try:
        budgets = load_award(args.award)
        transactions = load_transactions(args.transactions)
        deadlines = load_deadlines(args.schedule)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    budget_categories = set(budgets)
    award_total = money(sum(budgets.values(), Decimal("0.00")))
    as_of = args.asof if args.asof else max(t["period"] for t in transactions)

    timeline = build_timeline(transactions, budget_categories, award_total, args.months, as_of, deadlines)
    categories = category_summary(transactions, budgets, budget_categories)
    deadline_rows = deadline_status(deadlines, as_of)

    write_csv(args.timeline_out, TIMELINE_COLUMNS, timeline)
    write_csv(args.category_out, CATEGORY_COLUMNS, categories)
    write_csv(args.deadlines_out, DEADLINE_COLUMNS, deadline_rows)

    final = timeline[-1]
    rate = final["burn_rate"]
    runway = runway_periods(final["remaining"], rate)
    print("Grant drawdown and compliance")
    print("Award: %s over %d periods   As of period %d" % (award_total, args.months, as_of))
    print()
    print("Allowable drawn: %s   Disallowed: %s   Remaining: %s" % (
        final["cumulative_allowable"], final["cumulative_disallowed"], final["remaining"]))
    print("Burn rate: %s/period   Runway: %s more periods" % (rate, runway))
    print("Projected at award end: %s   Variance to award: %s   Status: %s" % (
        final["projected_total"], final["projected_variance"], final["status"]))
    print("Reports overdue: %d" % final["reports_overdue"])
    print()
    print("Wrote %s, %s, and %s" % (args.timeline_out, args.category_out, args.deadlines_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
