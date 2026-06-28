"""Command-line wrapper for the COGS and SKU profitability tool.

Reads the finished-unit costs from the batch tool, the excise summary from the
excise tool, and a sales file. Costs every sales line into production cost plus
excise, computes gross margin, prints margin by product line and channel, and
writes sku_margins.csv for the month-end close and the dashboard.

Usage:
    python cli.py --finished finished_unit_costs.csv --excise excise_summary.csv \
        --sales sales.csv --out sku_margins.csv
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

from margin import (
    by_channel,
    by_product_line,
    class_packaged_litres,
    cost_sales,
    excise_rate_per_litre,
    sku_cost_basis,
    totals,
)
from validation import ValidationError, validate

OUTPUT_COLUMNS = (
    "fg_sku", "product_line", "channel", "units_sold", "unit_price", "revenue",
    "cogs_production", "cogs_excise", "cogs_total", "gross_margin", "margin_pct",
)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [dict(r) for r in reader]
    return header, rows


def _format(value):
    return str(value) if isinstance(value, Decimal) else value


def write_output(path, lines):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_COLUMNS)
        for row in lines:
            writer.writerow([_format(row[c]) for c in OUTPUT_COLUMNS])


def print_block(title, key, rows):
    print("\n  %s" % title)
    print("  %-14s %10s %12s %12s %9s" % (key, "units", "revenue", "margin", "margin%"))
    print("  " + "-" * 60)
    for r in rows:
        print("  %-14s %10s %12s %12s %8s%%"
              % (r[key], r["units_sold"], r["revenue"], r["gross_margin"], r["margin_pct"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="COGS and SKU profitability.")
    parser.add_argument("--finished", required=True)
    parser.add_argument("--excise", required=True)
    parser.add_argument("--sales", required=True)
    parser.add_argument("--out", dest="out_path")
    args = parser.parse_args(argv)

    for path in (args.finished, args.excise, args.sales):
        if not os.path.exists(path):
            print("input file not found: %s" % path, file=sys.stderr)
            return 2

    _, finished_rows = read_rows(args.finished)
    _, excise_rows = read_rows(args.excise)
    sales_header, sales_rows = read_rows(args.sales)

    class_litres = class_packaged_litres(finished_rows)
    rates = excise_rate_per_litre(excise_rows, class_litres)
    basis = sku_cost_basis(finished_rows, rates)

    try:
        validate(sales_rows, sales_header, basis)
    except ValidationError as error:
        print("Input rejected. Nothing was written.\n", file=sys.stderr)
        for problem in error.problems:
            print("  - %s" % problem, file=sys.stderr)
        return 1

    sales = [{"fg_sku": r["fg_sku"].strip(), "channel": r["channel"].strip(),
              "units_sold": Decimal(r["units_sold"].strip()),
              "unit_price": Decimal(r["unit_price"].strip())} for r in sales_rows]
    lines = cost_sales(sales, basis)

    grand = totals(lines)
    print("COGS and SKU profitability")
    print("  sales lines    : %d" % len(lines))
    print("  revenue        : $%s" % grand["revenue"])
    print("  cost of goods  : $%s" % grand["cogs_total"])
    print("  gross margin   : $%s (%s%%)"
          % (grand["gross_margin"],
             (grand["gross_margin"] / grand["revenue"] * 100).quantize(Decimal("0.01")) if grand["revenue"] else 0))
    print_block("By product line", "product_line", by_product_line(lines))
    print_block("By channel", "channel", by_channel(lines))

    if args.out_path:
        write_output(args.out_path, lines)
        print("\nWrote %d rows to %s" % (len(lines), args.out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
