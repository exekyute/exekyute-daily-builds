"""Command-line entry point for the budget consolidation tool.

Reads every department CSV in a directory, standardizes the formatting, merges
the rows into one master budget, prints a summary, and writes the master file.

Example:
    python consolidate.py --departments data/departments --output output/master_budget.csv
"""

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

from consolidator import consolidate, format_amount
from loader import (
    BudgetFileError,
    discover_department_files,
    read_department_file,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Merge departmental budget sheets into one master budget template."
    )
    parser.add_argument(
        "--departments",
        default="data/departments",
        help="Directory of per-department budget CSV files (default: data/departments).",
    )
    parser.add_argument(
        "--output",
        default="output/master_budget.csv",
        help="Path for the consolidated master CSV (default: output/master_budget.csv).",
    )
    return parser


def write_master(rows, output_path):
    """Write the master rows to a CSV with a department,category,amount header."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["department", "category", "amount"])
        for row in rows:
            writer.writerow(
                [row["department"], row["category"], format_amount(row["amount"])]
            )


def print_table(rows):
    """Print the master budget as a GitHub-flavored markdown table."""
    print("| Department | Category | Amount |")
    print("| --- | --- | ---: |")
    for row in rows:
        print(f"| {row['department']} | {row['category']} | {format_amount(row['amount'])} |")


def print_summary(result, output_path):
    """Print the run counts and where the master file was written."""
    total = sum((row["amount"] for row in result.rows), start=Decimal("0"))
    print()
    print("Summary")
    print(f"  Departments processed: {result.departments}")
    print(f"  Master line items:     {result.line_items}")
    print(f"  Duplicate lines merged:{result.duplicates_merged:>2}")
    print(f"  Rows skipped (blank category): {result.skipped_blank_category}")
    print(f"  Rows skipped (unreadable amount): {result.skipped_bad_amount}")
    print(f"  Consolidated total:    {format_amount(total)}")
    print(f"  Master written to:     {output_path}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        files = discover_department_files(args.departments)
        if not files:
            print(f"No CSV files found in '{args.departments}'.", file=sys.stderr)
            return 1
        departments = [read_department_file(path) for path in files]
    except BudgetFileError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    result = consolidate(departments)
    print_table(result.rows)
    write_master(result.rows, args.output)
    print_summary(result, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
