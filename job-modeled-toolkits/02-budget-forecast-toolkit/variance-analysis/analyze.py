"""Command-line entry point for the variance analysis tool.

Reads the master budget and an actuals file, rolls both up by department,
computes the variance, prints a table and a written summary of the departments
that exceed budget parameters, and writes a CSV report.

Example:
    python analyze.py --budget data/master_budget.csv --actuals data/actuals.csv
"""

import argparse
import csv
import sys
from decimal import Decimal

from analyzer import analyze, format_amount
from loader import LedgerError, load_amounts


def build_parser():
    parser = argparse.ArgumentParser(
        description="Compare a master budget against actuals and flag departments over parameters."
    )
    parser.add_argument(
        "--budget",
        default="data/master_budget.csv",
        help="Master budget CSV from the consolidation tool (default: data/master_budget.csv).",
    )
    parser.add_argument(
        "--actuals",
        default="data/actuals.csv",
        help="Actual spend CSV (default: data/actuals.csv).",
    )
    parser.add_argument(
        "--pct-threshold",
        default="10",
        help="Percent over budget that trips a flag (default: 10).",
    )
    parser.add_argument(
        "--dollar-threshold",
        default="5000.00",
        help="Dollars over budget that trips a flag (default: 5000.00).",
    )
    parser.add_argument(
        "--report",
        default="variance_report.csv",
        help="Path for the CSV variance report (default: variance_report.csv).",
    )
    return parser


def print_table(result):
    print("| Department | Budget | Actual | Variance | Variance % | Status |")
    print("| --- | ---: | ---: | ---: | ---: | --- |")
    for line in result.departments:
        pct = "n/a" if line.variance_pct is None else f"{line.variance_pct}%"
        print(
            f"| {line.department} | {format_amount(line.budget)} | "
            f"{format_amount(line.actual)} | {format_amount(line.variance)} | "
            f"{pct} | {line.status} |"
        )


def print_summary(result, pct_threshold, dollar_threshold):
    print()
    print("Departments exceeding budget parameters")
    if result.flagged:
        for line in result.flagged:
            print(f"  {line.department}: {', '.join(line.reasons)}")
    else:
        print("  None. Every department is within parameters.")

    print()
    print("Findings")
    print(
        f"  Thresholds: {pct_threshold}% or {format_amount(dollar_threshold)} over budget."
    )
    print(f"  Departments flagged: {len(result.flagged)}")
    if result.missing_from_actuals:
        names = ", ".join(f"{d} / {c}" for d, c in result.missing_from_actuals)
        print(f"  Budgeted but missing from actuals: {names}")
    if result.unbudgeted:
        names = ", ".join(f"{d} / {c}" for d, c in result.unbudgeted)
        print(f"  Unbudgeted spend in actuals: {names}")
    print(f"  Duplicate actuals rows merged: {result.duplicates}")
    print(f"  Actuals rows skipped (blank or unreadable): {result.skipped}")


def write_report(result, report_path):
    with open(report_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["department", "budget", "actual", "variance", "variance_pct", "status"]
        )
        for line in result.departments:
            pct = "" if line.variance_pct is None else str(line.variance_pct)
            writer.writerow(
                [
                    line.department,
                    format_amount(line.budget),
                    format_amount(line.actual),
                    format_amount(line.variance),
                    pct,
                    line.status,
                ]
            )


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        pct_threshold = Decimal(args.pct_threshold)
        dollar_threshold = Decimal(args.dollar_threshold)
    except Exception:
        print("Error: thresholds must be numeric.", file=sys.stderr)
        return 1

    try:
        budget = load_amounts(args.budget, "budget")
        actuals = load_amounts(args.actuals, "actuals")
    except LedgerError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    result = analyze(budget.items, actuals.items, pct_threshold, dollar_threshold)
    result.duplicates = actuals.duplicates
    result.skipped = actuals.skipped

    print_table(result)
    print_summary(result, pct_threshold, dollar_threshold)
    write_report(result, args.report)
    print()
    print(f"Report written to: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
