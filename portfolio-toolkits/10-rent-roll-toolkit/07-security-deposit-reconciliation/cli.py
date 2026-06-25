"""Command-line wrapper for the security deposit reconciliation tool.

Reads a move-outs CSV, validates it, reconciles each deposit against its itemized
deductions, prints a readable table, and writes a reconciliation CSV. The math lives
in deposit_logic.py and the checks live in deposit_validation.py. This file only
handles input, output, and formatting.

Run from inside this folder:

    python cli.py
    python cli.py --input data/sample_moveouts.csv --output data/deposit_recon.csv
    python cli.py --input data/invalid_moveouts.csv
"""

import argparse
import csv
import os
import sys

import deposit_logic as logic
import deposit_validation as validation

DEFAULT_INPUT = os.path.join("data", "sample_moveouts.csv")
DEFAULT_OUTPUT = os.path.join("data", "deposit_recon.csv")

RECON_COLUMNS = [
    "unit",
    "tenant",
    "move_out_date",
    "deposit_held",
    "unpaid_rent",
    "cleaning",
    "damages",
    "total_deductions",
    "refund_due",
    "balance_owed",
    "result",
]


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


def build_reconciliation(move_outs):
    """Turn validated move-outs into reconciliation records, one per unit."""
    records = []
    for move_out in move_outs:
        deductions = logic.total_deductions(
            move_out.unpaid_rent, move_out.cleaning, move_out.damages
        )
        refund_due, balance_owed, result = logic.settle(move_out.deposit_held, deductions)
        records.append(
            {
                "unit": move_out.unit,
                "tenant": move_out.tenant,
                "move_out_date": move_out.move_out_date,
                "deposit_held": logic.quantize_money(move_out.deposit_held),
                "unpaid_rent": logic.quantize_money(move_out.unpaid_rent),
                "cleaning": logic.quantize_money(move_out.cleaning),
                "damages": logic.quantize_money(move_out.damages),
                "total_deductions": deductions,
                "refund_due": refund_due,
                "balance_owed": balance_owed,
                "result": result,
            }
        )
    return records


def write_reconciliation(path, records):
    """Write reconciliation records to CSV with fixed-point money and YYYY-MM-DD dates."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECON_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "unit": record["unit"],
                    "tenant": record["tenant"],
                    "move_out_date": record["move_out_date"].strftime("%Y-%m-%d"),
                    "deposit_held": "{0:.2f}".format(record["deposit_held"]),
                    "unpaid_rent": "{0:.2f}".format(record["unpaid_rent"]),
                    "cleaning": "{0:.2f}".format(record["cleaning"]),
                    "damages": "{0:.2f}".format(record["damages"]),
                    "total_deductions": "{0:.2f}".format(record["total_deductions"]),
                    "refund_due": "{0:.2f}".format(record["refund_due"]),
                    "balance_owed": "{0:.2f}".format(record["balance_owed"]),
                    "result": record["result"],
                }
            )


def print_table(records):
    """Print the reconciliation as an aligned console table."""
    header = [
        "UNIT",
        "TENANT",
        "MOVE OUT",
        "DEPOSIT",
        "DEDUCTIONS",
        "REFUND DUE",
        "BALANCE OWED",
        "RESULT",
    ]
    rows = [header]
    for record in records:
        rows.append(
            [
                record["unit"],
                record["tenant"],
                record["move_out_date"].strftime("%Y-%m-%d"),
                "{0:.2f}".format(record["deposit_held"]),
                "{0:.2f}".format(record["total_deductions"]),
                "{0:.2f}".format(record["refund_due"]),
                "{0:.2f}".format(record["balance_owed"]),
                record["result"],
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
        description="Reconcile security deposits against move-out deductions from a CSV."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="move-outs CSV to read")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="reconciliation CSV to write")
    args = parser.parse_args(argv)

    try:
        header, rows = read_csv(args.input)
        validation.check_header(header)
        move_outs, issues = validation.validate_rows(header, rows)
    except validation.ValidationError as error:
        print("Input rejected. Fix these problems and run again:", file=sys.stderr)
        for problem in error.problems:
            print("  - {0}".format(problem), file=sys.stderr)
        return 1

    records = build_reconciliation(move_outs)
    print_table(records)
    write_reconciliation(args.output, records)

    total_refunds = sum((record["refund_due"] for record in records), logic.ZERO)
    total_balances = sum((record["balance_owed"] for record in records), logic.ZERO)
    refunds = sum(1 for record in records if record["result"] == logic.RESULT_REFUND)
    balances = sum(1 for record in records if record["result"] == logic.RESULT_BALANCE)
    evens = sum(1 for record in records if record["result"] == logic.RESULT_EVEN)

    print("")
    print(
        "Reconciled {0} move-out(s). Refunds: {1} ({2:.2f}), balances owed: {3} ({4:.2f}), even: {5}".format(
            len(records), refunds, total_refunds, balances, total_balances, evens
        )
    )
    print("Reconciliation written to {0}".format(args.output))

    if issues:
        print("", file=sys.stderr)
        print("Skipped {0} row(s):".format(len(issues)), file=sys.stderr)
        for issue in issues:
            print("  - {0}".format(issue), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
