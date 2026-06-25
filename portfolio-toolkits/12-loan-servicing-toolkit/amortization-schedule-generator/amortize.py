"""Amortization Schedule Generator, command-line wrapper.

This file is a thin shell: it reads command-line arguments, runs validation,
calls the pure logic to build the schedule, writes the CSV, and prints a short
summary. The actual money math lives in ``schedule_logic.py`` and the rules live
in ``schedule_validation.py``.

Example:
    python amortize.py --principal 1000.00 --annual-rate 12 --term-months 6 \
        --output sample_data/schedule.csv
"""

import argparse
import csv
import sys

from schedule_logic import build_schedule
from schedule_validation import validate_inputs

CSV_HEADER = ["period", "payment", "interest", "principal", "balance"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a loan amortization schedule and write it to CSV."
    )
    parser.add_argument("--principal", required=True,
                        help="Loan amount in dollars, for example 1000.00.")
    parser.add_argument("--annual-rate", required=True,
                        help="Annual interest rate as a percent, for example 12.")
    parser.add_argument("--term-months", required=True,
                        help="Number of monthly payments, a whole number >= 1.")
    parser.add_argument("--output", required=True,
                        help="Path where the schedule CSV is written.")
    return parser.parse_args(argv)


def write_csv(path, rows):
    """Write the schedule rows to a CSV with fixed-point money values."""
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow([
                row["period"],
                f"{row['payment']:.2f}",
                f"{row['interest']:.2f}",
                f"{row['principal']:.2f}",
                f"{row['balance']:.2f}",
            ])


def main(argv=None):
    args = parse_args(argv)

    errors = validate_inputs(args.principal, args.annual_rate, args.term_months)
    if errors:
        print("Cannot build the schedule. Please fix the following:")
        for message in errors:
            print(f"  - {message}")
        return 1

    rows, summary = build_schedule(
        args.principal, args.annual_rate, args.term_months
    )

    try:
        write_csv(args.output, rows)
    except OSError as error:
        print(f"Could not write the output file: {error}")
        return 1

    print(f"Wrote {len(rows)} periods to {args.output}")
    print(f"  Level payment:     {summary['level_payment']:.2f}")
    print(f"  Total interest:    {summary['total_interest']:.2f}")
    print(f"  Total of payments: {summary['total_paid']:.2f}")
    print(f"  Final balance:     {rows[-1]['balance']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
