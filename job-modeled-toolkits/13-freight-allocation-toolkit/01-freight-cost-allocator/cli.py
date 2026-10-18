"""Command-line wrapper for the Freight Cost Allocator.

This file handles all input and output: parsing arguments, reading the
shipment CSV, calling the pure logic in allocator_logic.py, printing a readable
table, and writing the landed-cost CSV. The business rules live in
allocator_logic.py and are covered by test_allocator_logic.py.

Examples
--------
    python cli.py --freight 100.00 --basis value
    python cli.py --freight 100.00 --basis weight
    python cli.py --input data/invalid_shipment.csv
"""

import argparse
import csv
import os
import sys

import allocator_logic as logic


def note_blank_lines(lines, blank_lines):
    """Yield each line of a file unchanged, noting the empty ones.

    Adds the 1-based number of every line that holds only a line ending to the
    blank_lines set. DictReader skips such a line when it falls between rows.
    """
    for number, line in enumerate(lines, start=1):
        if line in ("\n", "\r\n", "\r"):
            blank_lines.add(number)
        yield line


def read_rows(path):
    """Read a shipment CSV into (fieldnames, rows).

    rows is a list of (line_number, record) tuples. line_number is the 1-based
    file line the row starts on. The header is line 1, and blank lines and the
    extra lines of a quoted field that runs over several lines count too.
    """
    with open(path, newline="", encoding="utf-8-sig") as handle:
        blank_lines = set()
        reader = csv.DictReader(
            note_blank_lines(handle, blank_lines),
            restkey=logic.EXTRA_KEY,
            restval=None,
        )
        fieldnames = reader.fieldnames
        rows = []
        # reader.line_num is the last file line read so far, so a row starts on
        # the first line past the previous row (or the header) that is not blank.
        last_line = reader.line_num
        for record in reader:
            line_number = last_line + 1
            while line_number in blank_lines:
                line_number += 1
            rows.append((line_number, record))
            last_line = reader.line_num
    return fieldnames, rows


def print_table(line_items, allocations, basis):
    """Print a readable allocation table and a reconciling summary line."""
    headers = [
        "line_id",
        "description",
        "qty",
        "unit_cost",
        basis,
        "freight",
        "landed_unit",
    ]
    rows = []
    for item, allocation in zip(line_items, allocations):
        basis_display = (
            logic.format_cents(logic.to_cents(item.basis_amount(basis)))
            if basis == "value"
            else "{0:.2f}".format(item.weight)
        )
        rows.append(
            [
                item.line_id,
                item.description,
                str(item.quantity),
                logic.format_cents(logic.to_cents(item.unit_cost)),
                basis_display,
                logic.format_cents(allocation),
                logic.format_cents(logic.landed_unit_cost_cents(item, allocation)),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def render(cells):
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells))

    print(render(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(render(row))


def write_landed_csv(path, line_items, allocations):
    """Write the landed-cost CSV, creating the output directory if needed."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    header, rows = logic.build_landed_rows(line_items, allocations)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Allocate a shipment's freight charge across its line items."
    )
    parser.add_argument(
        "--freight",
        default="100.00",
        help="Total freight charge in dollars (default: 100.00).",
    )
    parser.add_argument(
        "--basis",
        choices=logic.VALID_BASES,
        default="value",
        help="Allocation basis: weight or value (default: value).",
    )
    parser.add_argument(
        "--input",
        default=os.path.join("data", "sample_shipment.csv"),
        help="Path to the shipment line-items CSV.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("out", "landed_cost.csv"),
        help="Path to write the landed-cost CSV.",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.input):
        print("Error: input file not found: {0}".format(args.input), file=sys.stderr)
        return 1

    try:
        fieldnames, rows = read_rows(args.input)
    except OSError as error:
        print("Error: could not read {0}: {1}".format(args.input, error), file=sys.stderr)
        return 1

    missing = logic.missing_columns(fieldnames)
    if missing:
        print(
            "Error: input is missing required column(s): {0}".format(
                ", ".join(missing)
            ),
            file=sys.stderr,
        )
        return 1

    try:
        freight_cents = logic.parse_freight_cents(args.freight)
        line_items = logic.build_line_items(rows)
        allocations = logic.allocate(line_items, freight_cents, args.basis)
    except logic.ValidationError as error:
        print(
            "Found {0} problem(s) in the input:".format(len(error.problems)),
            file=sys.stderr,
        )
        for problem in error.problems:
            print("  - {0}".format(problem), file=sys.stderr)
        return 1

    print(
        "Shipment freight allocation by {0}  (freight charge: {1})".format(
            args.basis, logic.format_cents(freight_cents)
        )
    )
    print()
    print_table(line_items, allocations, args.basis)
    print()

    total_allocated = sum(allocations)
    print(
        "Freight entered: {0}    Total allocated: {1}    Match: {2}".format(
            logic.format_cents(freight_cents),
            logic.format_cents(total_allocated),
            "yes" if total_allocated == freight_cents else "NO",
        )
    )

    write_landed_csv(args.output, line_items, allocations)
    print("Landed-cost CSV written to: {0}".format(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
