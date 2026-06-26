"""Command-line wrapper for the capital call allocator.

This file is deliberately thin. It reads the commitments CSV, hands the data to
the validation and logic modules, and writes the allocation CSV. All of the
calculation lives in allocator_logic.py and all of the input checks live in
allocator_validation.py.

Usage:
    python allocate.py --call-total 250000.00 \
        --commitments sample_data/commitments.csv \
        --output sample_data/allocation.csv
"""

import argparse
import csv
import sys
from decimal import Decimal

import allocator_logic
import allocator_validation


def read_commitments(path):
    """Read a commitments CSV into (header, rows) of raw strings.

    Returns (None, []) when the file holds no rows at all.
    """
    with open(path, newline="", encoding="utf-8") as handle:
        records = list(csv.reader(handle))
    if not records:
        return None, []
    return records[0], records[1:]


def write_allocation(path, allocations):
    """Write the per-investor allocation CSV with fixed-point dollar values."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["investor", "commitment", "ownership_pct", "called_amount"])
        for row in allocations:
            writer.writerow(
                [
                    row["investor"],
                    format(row["commitment"], "f"),
                    format(row["ownership_pct"], "f"),
                    format(row["called_amount"], "f"),
                ]
            )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Allocate a fund capital call across investors pro-rata by commitment "
            "and write a per-investor allocation CSV."
        )
    )
    parser.add_argument(
        "--call-total",
        required=True,
        help="Total capital call amount in dollars, for example 250000.00",
    )
    parser.add_argument(
        "--commitments",
        required=True,
        help="Path to the investor commitments CSV (header: investor,commitment).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the per-investor allocation CSV.",
    )
    args = parser.parse_args(argv)

    errors = []

    call_total, call_errors = allocator_validation.validate_call_total(args.call_total)
    errors.extend(call_errors)

    try:
        header, rows = read_commitments(args.commitments)
    except FileNotFoundError:
        print(
            f"Error: commitments file not found: {args.commitments}",
            file=sys.stderr,
        )
        return 1

    _, row_errors = allocator_validation.validate_commitments(header, rows)
    errors.extend(row_errors)

    if errors:
        print(
            "Allocation rejected. Please fix the following and run again:",
            file=sys.stderr,
        )
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 1

    # Re-collect the clean commitments now that validation has passed.
    commitments, _ = allocator_validation.validate_commitments(header, rows)
    allocations = allocator_logic.allocate_call(call_total, commitments)
    write_allocation(args.output, allocations)

    total_called = sum(row["called_amount"] for row in allocations)
    print(
        f"Allocated {format(call_total.quantize(Decimal('0.01')), 'f')} "
        f"across {len(allocations)} investors."
    )
    print(f"Sum of called amounts: {format(total_called, 'f')}")
    print(f"Allocation written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
