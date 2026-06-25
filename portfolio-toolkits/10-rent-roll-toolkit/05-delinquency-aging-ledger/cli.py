"""Command-line wrapper for the delinquency and aging ledger.

Reads a charges ledger CSV, validates it, computes each unit's open balance, ages it
into a bucket, applies a late fee once past the grace period, totals what is owed, and
writes an aging report CSV. The math lives in aging_logic.py and the checks live in
aging_validation.py. This file only handles input, output, and formatting.

Charges that are well formed but fully paid (no open balance) are left off the report
as settled, and counted in the footer. Run from inside this folder:

    python cli.py
    python cli.py --as-of 2026-06-12 --grace-days 5 --late-fee-rate 0.05
    python cli.py --input data/sample_ledger.csv --output data/aging.csv
    python cli.py --input data/invalid_ledger.csv
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from decimal import Decimal

import aging_logic as logic
import aging_validation as validation

DEFAULT_INPUT = os.path.join("data", "sample_ledger.csv")
DEFAULT_OUTPUT = os.path.join("data", "aging.csv")
DEFAULT_AS_OF = "2026-06-12"
DEFAULT_GRACE_DAYS = 5
DEFAULT_LATE_FEE_RATE = "0.05"

AGING_COLUMNS = [
    "unit",
    "tenant",
    "charge_type",
    "due_date",
    "balance",
    "days_overdue",
    "bucket",
    "late_fee",
    "total_owed",
]


def parse_as_of(text):
    """Parse the as-of date. Raises ValidationError if it is not YYYY-MM-DD."""
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise validation.ValidationError(
            ["--as-of must be in YYYY-MM-DD form, for example 2026-06-12"]
        )


def read_csv(path):
    """Read a CSV into (header, rows). Raises ValidationError for missing or empty files."""
    if not os.path.isfile(path):
        raise validation.ValidationError(["input file not found: {0}".format(path)])
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        all_rows = [row for row in reader if row != []]
    if not all_rows:
        raise validation.ValidationError(["input file is empty: {0}".format(path)])
    return all_rows[0], all_rows[1:]


def build_aging(charges, as_of, grace_days, rate):
    """Turn validated charges into aging records and a count of settled charges.

    A charge with no open balance (paid in full or overpaid) is settled and left off
    the report. Returns (records, settled_count).
    """
    records = []
    settled = 0
    for charge in charges:
        open_balance = logic.balance(charge.amount_charged, charge.amount_paid)
        if open_balance <= logic.ZERO:
            settled += 1
            continue
        overdue = logic.days_overdue(as_of, charge.due_date)
        fee = logic.late_fee(open_balance, overdue, grace_days, rate)
        records.append(
            {
                "unit": charge.unit,
                "tenant": charge.tenant,
                "charge_type": charge.charge_type,
                "due_date": charge.due_date,
                "balance": open_balance,
                "days_overdue": overdue,
                "bucket": logic.bucket_for(overdue),
                "late_fee": fee,
                "total_owed": logic.total_owed(open_balance, fee),
            }
        )
    return records, settled


def write_aging(path, records):
    """Write aging records to CSV with fixed-point money and YYYY-MM-DD dates."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AGING_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "unit": record["unit"],
                    "tenant": record["tenant"],
                    "charge_type": record["charge_type"],
                    "due_date": record["due_date"].strftime("%Y-%m-%d"),
                    "balance": "{0:.2f}".format(record["balance"]),
                    "days_overdue": record["days_overdue"],
                    "bucket": record["bucket"],
                    "late_fee": "{0:.2f}".format(record["late_fee"]),
                    "total_owed": "{0:.2f}".format(record["total_owed"]),
                }
            )


def print_table(records):
    """Print the aging report as an aligned console table."""
    header = [
        "UNIT",
        "TENANT",
        "CHARGE",
        "DUE DATE",
        "BALANCE",
        "OVERDUE",
        "BUCKET",
        "LATE FEE",
        "TOTAL OWED",
    ]
    rows = [header]
    for record in records:
        rows.append(
            [
                record["unit"],
                record["tenant"],
                record["charge_type"],
                record["due_date"].strftime("%Y-%m-%d"),
                "{0:.2f}".format(record["balance"]),
                str(record["days_overdue"]),
                record["bucket"],
                "{0:.2f}".format(record["late_fee"]),
                "{0:.2f}".format(record["total_owed"]),
            ]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    for line_index, row in enumerate(rows):
        cells = [row[i].ljust(widths[i]) for i in range(len(row))]
        print("  ".join(cells))
        if line_index == 0:
            print("  ".join("-" * widths[i] for i in range(len(header))))


def print_bucket_totals(records):
    """Print one line per bucket with its count and total owed, in aging order."""
    totals = {bucket: {"count": 0, "owed": logic.ZERO} for bucket in logic.BUCKET_ORDER}
    for record in records:
        totals[record["bucket"]]["count"] += 1
        totals[record["bucket"]]["owed"] += record["total_owed"]
    print("Aging buckets:")
    for bucket in logic.BUCKET_ORDER:
        print(
            "  {0:<8} {1:>2} charge(s)  {2:>12.2f}".format(
                bucket, totals[bucket]["count"], totals[bucket]["owed"]
            )
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Age overdue charges into buckets and apply late fees from a ledger CSV."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="ledger CSV to read")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="aging CSV to write")
    parser.add_argument("--as-of", default=DEFAULT_AS_OF, help="reference date in YYYY-MM-DD form")
    parser.add_argument(
        "--grace-days",
        type=int,
        default=DEFAULT_GRACE_DAYS,
        help="days past due before a late fee starts to accrue",
    )
    parser.add_argument(
        "--late-fee-rate",
        default=DEFAULT_LATE_FEE_RATE,
        help="late fee as a fraction of the open balance, for example 0.05 for 5 percent",
    )
    args = parser.parse_args(argv)

    try:
        as_of = parse_as_of(args.as_of)
        rate = Decimal(args.late_fee_rate)
        header, rows = read_csv(args.input)
        validation.check_header(header)
        charges, issues = validation.validate_rows(header, rows)
    except validation.ValidationError as error:
        print("Input rejected. Fix these problems and run again:", file=sys.stderr)
        for problem in error.problems:
            print("  - {0}".format(problem), file=sys.stderr)
        return 1

    records, settled = build_aging(charges, as_of, args.grace_days, rate)
    print_table(records)
    write_aging(args.output, records)

    total_owed = sum((record["total_owed"] for record in records), logic.ZERO)

    print("")
    print_bucket_totals(records)
    print("")
    print(
        "Aged {0} delinquent charge(s) as of {1}. Total owed: {2:.2f}. Settled (left off): {3}".format(
            len(records), as_of.strftime("%Y-%m-%d"), total_owed, settled
        )
    )
    print("Aging report written to {0}".format(args.output))

    if issues:
        print("", file=sys.stderr)
        print("Skipped {0} row(s):".format(len(issues)), file=sys.stderr)
        for issue in issues:
            print("  - {0}".format(issue), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
