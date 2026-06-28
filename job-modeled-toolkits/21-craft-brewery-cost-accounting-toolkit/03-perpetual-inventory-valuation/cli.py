"""Command-line wrapper for the perpetual inventory valuation tool.

Reads a transaction ledger (opening balances, receipts from the procurement
tool, issues to production, finished-goods receipts from the batch tool, and
finished-goods shipments), replays it under the perpetual weighted-average
method, prints a valuation by category, and writes perpetual_valuation.csv for
the month-end close to reconcile against the physical count.

Usage:
    python cli.py --in transactions.csv --out perpetual_valuation.csv
    python cli.py --in transactions.csv
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

from valuation import money, totals_by_category, value_inventory
from validation import ValidationError, validate

OUTPUT_COLUMNS = (
    "sku", "description", "category", "on_hand_qty", "unit",
    "wac_unit_cost", "inventory_value", "integrity_flag",
)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [dict(r) for r in reader]
    return header, rows


def to_typed(rows):
    out = []
    for r in rows:
        out.append({
            "txn_id": r["txn_id"].strip(),
            "sku": r["sku"].strip(),
            "description": r["description"].strip(),
            "category": r["category"].strip(),
            "txn_type": r["txn_type"].strip(),
            "quantity": Decimal(r["quantity"].strip()),
            "unit": r["unit"].strip(),
            "value": Decimal((r["value"].strip() or "0")),
        })
    return out


def _format(value):
    return str(value) if isinstance(value, Decimal) else value


def write_output(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_COLUMNS)
        for row in rows:
            writer.writerow([_format(row[c]) for c in OUTPUT_COLUMNS])


def print_summary(rows):
    by_cat, grand = totals_by_category(rows)
    print("Perpetual inventory valuation")
    print("  SKUs valued    : %d" % len(rows))
    for category in ("raw_material", "packaging_material", "finished_goods"):
        if category in by_cat:
            print("  %-20s : $%s" % (category, by_cat[category]))
    print("  %-20s : $%s" % ("total inventory", grand))
    print("")
    print("  %-16s %-18s %12s %12s %14s" % ("sku", "category", "on hand", "unit cost", "value"))
    print("  " + "-" * 76)
    for row in rows:
        print("  %-16s %-18s %12s %12s %14s"
              % (row["sku"], row["category"], row["on_hand_qty"],
                 row["wac_unit_cost"], row["inventory_value"]))
        if row["integrity_flag"]:
            print("    ! %s: %s" % (row["sku"], row["integrity_flag"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Perpetual inventory valuation.")
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--out", dest="out_path")
    args = parser.parse_args(argv)

    if not os.path.exists(args.in_path):
        print("input file not found: %s" % args.in_path, file=sys.stderr)
        return 2

    header, rows = read_rows(args.in_path)
    try:
        validate(rows, header)
    except ValidationError as error:
        print("Input rejected. Nothing was written.\n", file=sys.stderr)
        for problem in error.problems:
            print("  - %s" % problem, file=sys.stderr)
        return 1

    valued = value_inventory(to_typed(rows))
    print_summary(valued)

    if args.out_path:
        write_output(args.out_path, valued)
        print("\nWrote %d rows to %s" % (len(valued), args.out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
