"""Command-line entry point for the Ledger Reconciliation Tool.

Reads the internal payroll file and the trustee file, compares them by Employee
ID, prints a markdown variance table plus a summary line, and writes the same
table to a CSV report.

Example
-------
    python reconcile.py \
        --internal data/internal_payroll.csv \
        --trustee data/trustee_assets.csv
"""

import argparse
import csv
import sys
from decimal import Decimal

from loader import load_ledger, LedgerError
from reconciler import reconcile, summarize


def format_markdown_table(lines):
    """Render the reconciliation lines as a GitHub-flavored markdown table."""
    header = (
        "| Employee ID | Name | Internal | Trustee | Variance | Status |\n"
        "| --- | --- | ---: | ---: | ---: | --- |"
    )
    rows = [
        f"| {line.employee_id} | {line.name} | "
        f"{line.internal_amount:.2f} | {line.trustee_amount:.2f} | "
        f"{line.variance:.2f} | {line.status} |"
        for line in lines
    ]
    return "\n".join([header, *rows])


def write_csv_report(path, lines):
    """Write the reconciliation lines to a CSV report for the record."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["employee_id", "name", "internal_amount", "trustee_amount", "variance", "status"]
        )
        for line in lines:
            writer.writerow(
                [
                    line.employee_id,
                    line.name,
                    f"{line.internal_amount:.2f}",
                    f"{line.trustee_amount:.2f}",
                    f"{line.variance:.2f}",
                    line.status,
                ]
            )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Reconcile an internal payroll ledger against a trustee ledger."
    )
    parser.add_argument("--internal", required=True, help="Path to internal_payroll.csv")
    parser.add_argument("--trustee", required=True, help="Path to trustee_assets.csv")
    parser.add_argument(
        "--tolerance",
        default="0.01",
        help="Maximum absolute difference still treated as a match (default 0.01).",
    )
    parser.add_argument(
        "--report",
        default="variance_report.csv",
        help="Where to write the CSV report (default variance_report.csv).",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        tolerance = Decimal(str(args.tolerance))
        internal = load_ledger(args.internal, required_columns=["employee_id", "name", "amount"])
        trustee = load_ledger(args.trustee, required_columns=["employee_id", "amount"])
    except LedgerError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 1

    lines = reconcile(internal, trustee, tolerance=tolerance)
    counts = summarize(lines, internal, trustee)

    print("Ledger Reconciliation Report")
    print("============================")
    print(format_markdown_table(lines))
    print()
    print(
        "Summary: "
        f"{counts['Matched']} matched, "
        f"{counts['Variance']} variance, "
        f"{counts['Missing in trustee']} missing in trustee, "
        f"{counts['Missing in internal']} missing in internal, "
        f"{counts['duplicates']} duplicate id(s), "
        f"{counts['skipped']} skipped row(s)."
    )

    write_csv_report(args.report, lines)
    print(f"\nCSV report written to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
