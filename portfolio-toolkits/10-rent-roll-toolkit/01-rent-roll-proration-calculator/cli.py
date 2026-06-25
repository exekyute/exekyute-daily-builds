"""Command-line wrapper for the rent roll and proration calculator.

Reads a leases CSV, validates it, builds the per-unit rent roll for one billing
month, prints a readable table, and writes the rent roll to CSV. The math lives in
rent_roll_logic.py and the checks live in rent_roll_validation.py. This file only
handles input, output, and formatting.

Run from inside this folder:

    python cli.py
    python cli.py --month 2026-06 --late-fee-rate 0.05
    python cli.py --input data/sample_leases.csv --output data/sample_rent_roll.csv
    python cli.py --input data/invalid_leases.csv
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

import rent_roll_logic as logic
import rent_roll_validation as validation

DEFAULT_INPUT = os.path.join("data", "sample_leases.csv")
DEFAULT_OUTPUT = os.path.join("data", "sample_rent_roll.csv")
DEFAULT_MONTH = "2026-06"
DEFAULT_LATE_FEE_RATE = "0.05"

# The shared rent roll header. The companion dashboard reads a subset of these and
# ignores the rest, so the richer audit columns ride along without breaking it.
RENT_ROLL_COLUMNS = [
    "unit",
    "tenant",
    "monthly_rent",
    "billing_month",
    "days_in_month",
    "occupied_days",
    "prorated_rent",
    "overdue_balance",
    "late_fee",
    "amount_due",
    "lease_end",
]


def parse_month(text):
    """Parse a 'YYYY-MM' string into (year, month). Raises ValidationError if bad."""
    try:
        year_text, month_text = text.strip().split("-")
        year = int(year_text)
        month = int(month_text)
        if not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        raise validation.ValidationError(
            ["--month must be in YYYY-MM form, for example 2026-06"]
        )
    return year, month


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


def build_rent_roll(leases, year, month, late_fee_rate):
    """Turn validated leases into rent roll records, one dict per unit."""
    total_days = logic.days_in_month(year, month)
    billing_month = "{0:04d}-{1:02d}".format(year, month)
    records = []
    for lease in leases:
        occupied = logic.occupied_days(year, month, lease.move_in, lease.move_out)
        prorated = logic.prorate_rent(lease.monthly_rent, occupied, total_days)
        fee = logic.late_fee(lease.overdue_balance, late_fee_rate)
        due = logic.amount_due(prorated, lease.overdue_balance, fee)
        records.append(
            {
                "unit": lease.unit,
                "tenant": lease.tenant,
                "monthly_rent": logic.quantize_money(lease.monthly_rent),
                "billing_month": billing_month,
                "days_in_month": total_days,
                "occupied_days": occupied,
                "prorated_rent": prorated,
                "overdue_balance": logic.quantize_money(lease.overdue_balance),
                "late_fee": fee,
                "amount_due": due,
                "lease_end": lease.lease_end.strftime("%Y-%m-%d"),
            }
        )
    return records


def write_rent_roll(path, records):
    """Write rent roll records to CSV with fixed-point money text."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RENT_ROLL_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "unit": record["unit"],
                    "tenant": record["tenant"],
                    "monthly_rent": "{0:.2f}".format(record["monthly_rent"]),
                    "billing_month": record["billing_month"],
                    "days_in_month": record["days_in_month"],
                    "occupied_days": record["occupied_days"],
                    "prorated_rent": "{0:.2f}".format(record["prorated_rent"]),
                    "overdue_balance": "{0:.2f}".format(record["overdue_balance"]),
                    "late_fee": "{0:.2f}".format(record["late_fee"]),
                    "amount_due": "{0:.2f}".format(record["amount_due"]),
                    "lease_end": record["lease_end"],
                }
            )


def print_table(records):
    """Print the rent roll as an aligned console table."""
    header = [
        "UNIT",
        "TENANT",
        "RENT",
        "DAYS",
        "PRORATED",
        "OVERDUE",
        "LATE FEE",
        "AMOUNT DUE",
        "LEASE END",
    ]
    rows = [header]
    for record in records:
        rows.append(
            [
                record["unit"],
                record["tenant"],
                "{0:.2f}".format(record["monthly_rent"]),
                "{0}/{1}".format(record["occupied_days"], record["days_in_month"]),
                "{0:.2f}".format(record["prorated_rent"]),
                "{0:.2f}".format(record["overdue_balance"]),
                "{0:.2f}".format(record["late_fee"]),
                "{0:.2f}".format(record["amount_due"]),
                record["lease_end"],
            ]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    for line_index, row in enumerate(rows):
        cells = [row[i].ljust(widths[i]) for i in range(len(row))]
        print("  ".join(cells))
        if line_index == 0:
            print("  ".join("-" * widths[i] for i in range(len(header))))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a per-unit rent roll from a leases CSV, prorating partial months and applying late fees."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="leases CSV to read")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="rent roll CSV to write")
    parser.add_argument("--month", default=DEFAULT_MONTH, help="billing month in YYYY-MM form")
    parser.add_argument(
        "--late-fee-rate",
        default=DEFAULT_LATE_FEE_RATE,
        help="late fee as a fraction of the overdue balance, for example 0.05 for 5 percent",
    )
    args = parser.parse_args(argv)

    try:
        year, month = parse_month(args.month)
        late_fee_rate = Decimal(args.late_fee_rate)
        header, rows = read_csv(args.input)
        validation.check_header(header)
        leases, issues = validation.validate_rows(header, rows)
    except validation.ValidationError as error:
        print("Input rejected. Fix these problems and run again:", file=sys.stderr)
        for problem in error.problems:
            print("  - {0}".format(problem), file=sys.stderr)
        return 1

    records = build_rent_roll(leases, year, month, late_fee_rate)
    print_table(records)

    write_rent_roll(args.output, records)
    total_billed = sum((record["amount_due"] for record in records), logic.ZERO)

    print("")
    print(
        "Billed {0} unit(s) for {1:04d}-{2:02d}. Total billed: {3:.2f}".format(
            len(records), year, month, total_billed
        )
    )
    print("Rent roll written to {0}".format(args.output))

    if issues:
        print("", file=sys.stderr)
        print("Skipped {0} row(s):".format(len(issues)), file=sys.stderr)
        for issue in issues:
            print("  - {0}".format(issue), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
