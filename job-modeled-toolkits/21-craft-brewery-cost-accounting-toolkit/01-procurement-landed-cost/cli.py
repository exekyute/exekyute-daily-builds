"""Command-line wrapper for the procurement landed-cost engine.

Reads a purchase-order CSV, validates it, folds freight and import duty into the
landed cost of each line, prints a short summary, and writes landed_costs.csv for
the batch costing and valuation tools to consume.

Usage:
    python cli.py --in sample_purchase_orders.csv --out landed_costs.csv
    python cli.py --in sample_purchase_orders.csv          (prints, no file written)
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

from landed import cost_all, money
from validation import ValidationError, validate

OUTPUT_COLUMNS = (
    "po_id",
    "line_id",
    "sku",
    "description",
    "category",
    "quantity",
    "unit",
    "unit_price",
    "extended_value",
    "freight_alloc",
    "duty",
    "landed_total",
    "landed_unit_cost",
)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return header, rows


def to_decimal_rows(rows):
    """Turn validated string rows into the dicts the logic expects."""
    out = []
    for row in rows:
        out.append(
            {
                "po_id": row["po_id"].strip(),
                "line_id": row["line_id"].strip(),
                "sku": row["sku"].strip(),
                "description": row["description"].strip(),
                "category": row["category"].strip(),
                "quantity": Decimal(row["quantity"].strip()),
                "unit": row["unit"].strip(),
                "unit_price": Decimal(row["unit_price"].strip()),
                "freight_total": Decimal((row["freight_total"].strip() or "0")),
                "duty_rate": Decimal((row["duty_rate"].strip() or "0")),
            }
        )
    return out


def write_output(path, results):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_COLUMNS)
        for row in results:
            writer.writerow([_format(row[col]) for col in OUTPUT_COLUMNS])


def _format(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


def print_summary(results):
    freight = money(sum(r["freight_alloc"] for r in results))
    duty = money(sum(r["duty"] for r in results))
    landed = money(sum(r["landed_total"] for r in results))
    print("Landed cost summary")
    print("  purchase order lines : %d" % len(results))
    print("  freight allocated    : $%s" % freight)
    print("  import duty           : $%s" % duty)
    print("  total landed cost     : $%s" % landed)
    print("")
    print("  %-14s %-16s %12s %12s" % ("sku", "category", "qty", "unit cost"))
    print("  " + "-" * 56)
    for row in results:
        print(
            "  %-14s %-16s %12s %12s"
            % (row["sku"], row["category"], row["quantity"], row["landed_unit_cost"])
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Procurement landed-cost engine.")
    parser.add_argument("--in", dest="in_path", required=True, help="purchase-order CSV")
    parser.add_argument("--out", dest="out_path", help="where to write landed_costs.csv")
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

    results = cost_all(to_decimal_rows(rows))
    print_summary(results)

    if args.out_path:
        write_output(args.out_path, results)
        print("\nWrote %d rows to %s" % (len(results), args.out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
