"""Command-line wrapper for the AR Aging and Late-Fee Engine.

This file is intentionally thin. It reads the input CSV, hands each row to the
validation module, ages the accepted invoices with the aging module, writes the
aging report CSV, and prints a summary. All rules live in aging.py and
validation.py.

Usage:
    python cli.py --input sample-data/open-invoices.csv \\
                  --output sample-data/aging-report.csv \\
                  --reference-date 2026-06-12 --rate 0.015
"""

import argparse
import csv
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import aging
import validation

DEFAULT_RATE = Decimal("0.015")


def parse_reference_date(value):
    """argparse type: a YYYY-MM-DD reference date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"reference-date must be YYYY-MM-DD, got {value!r}")


def parse_rate(value):
    """argparse type: a non-negative decimal fee rate (0.015 means 1.5%)."""
    try:
        rate = Decimal(value)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"rate must be a number, got {value!r}")
    if rate < 0:
        raise argparse.ArgumentTypeError(f"rate must be 0 or greater, got {value!r}")
    return rate


def build_parser():
    parser = argparse.ArgumentParser(
        description="Bucket open invoices by age and apply a late fee to overdue ones."
    )
    parser.add_argument(
        "--input",
        default="sample-data/open-invoices.csv",
        help="path to the open-invoices CSV (default: sample-data/open-invoices.csv)",
    )
    parser.add_argument(
        "--output",
        default="sample-data/aging-report.csv",
        help="path to write the aging report CSV (default: sample-data/aging-report.csv)",
    )
    parser.add_argument(
        "--reference-date",
        type=parse_reference_date,
        default=date.today(),
        help="date to age invoices against in YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--rate",
        type=parse_rate,
        default=DEFAULT_RATE,
        help="late-fee rate applied to overdue invoices (default: 0.015 = 1.5%%)",
    )
    return parser


def read_invoices(path):
    """Read and validate the input CSV.

    Returns (invoices, rejects) where rejects is a list of
    (line_number, raw_fields, reason) tuples. Raises RowError if the header is
    wrong and SystemExit-style errors are handled by the caller.
    """
    invoices = []
    rejects = []
    seen_numbers = set()

    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise validation.RowError("input file is empty")
        validation.validate_header(header)

        for line_number, fields in enumerate(reader, start=2):
            if not fields:
                continue  # skip blank lines
            try:
                invoices.append(validation.validate_row(fields, seen_numbers))
            except validation.RowError as error:
                rejects.append((line_number, fields, str(error)))

    return invoices, rejects


def write_report(path, aged):
    """Write the aging report CSV with money as fixed-point strings."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(aging.OUTPUT_HEADER)
        for item in aged:
            writer.writerow(
                [
                    item.invoice_number,
                    item.customer,
                    item.issue_date.isoformat(),
                    item.due_date.isoformat(),
                    aging.money(item.amount),
                    item.days_past_due,
                    item.aging_bucket,
                    aging.money(item.late_fee),
                    aging.money(item.total_due),
                ]
            )


def print_summary(aged, rejects, reference_date, rate):
    """Print a per-bucket collection summary and any rejected rows."""
    summary = aging.summarize(aged)
    print(f"Aging report as of {reference_date.isoformat()} (late-fee rate {rate})")
    print(f"{len(aged)} invoice(s) aged, {len(rejects)} row(s) rejected")
    print()
    print(f"{'Bucket':<10} {'Count':>6} {'Total outstanding':>20}")
    print("-" * 38)
    for bucket in aging.BUCKETS:
        entry = summary[bucket]
        print(f"{bucket:<10} {entry['count']:>6} {aging.money(entry['total']):>20}")
    print("-" * 38)
    total = aging.grand_total(aged)
    print(f"{'Grand total':<10} {len(aged):>6} {aging.money(total):>20}")

    if rejects:
        print("\nRejected rows (not written to the report):", file=sys.stderr)
        for line_number, fields, reason in rejects:
            raw = ",".join(fields)
            print(f"  line {line_number}: {reason}  [{raw}]", file=sys.stderr)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        invoices, rejects = read_invoices(args.input)
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2
    except validation.RowError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    aged = aging.age_invoices(invoices, args.reference_date, args.rate)
    write_report(args.output, aged)
    print_summary(aged, rejects, args.reference_date, args.rate)
    print()
    print(f"Wrote {len(aged)} aged invoice(s) to {args.output}")

    # A non-zero exit signals that some rows were rejected, while the valid rows
    # are still written to the report.
    return 1 if rejects else 0


if __name__ == "__main__":
    raise SystemExit(main())
