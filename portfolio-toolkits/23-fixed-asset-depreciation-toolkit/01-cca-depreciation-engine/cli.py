"""Command-line wrapper for the fixed-asset depreciation engine.

Reads an asset register and an opening-UCC file, validates every row, runs the
book and CCA calculations, and writes two output files:

  per_asset_schedule.csv  - straight-line book depreciation for each asset.
  per_class_cca.csv       - the CCA rollforward for each class pool.

Usage:
  python cli.py --assets sample_assets.csv --opening opening_ucc.csv
  python cli.py --assets sample_assets.csv --opening opening_ucc.csv --year 2026

The output files are written next to this script. The default tax year is 2026.
"""

import argparse
import csv
import sys
from decimal import Decimal

from cca import compute_schedules
from validation import validate_asset_row, validate_opening_row, ValidationError

DEFAULT_TAX_YEAR = 2026

PER_ASSET_COLUMNS = [
    "asset_id",
    "description",
    "cca_class",
    "capital_cost",
    "salvage_value",
    "useful_life_years",
    "in_service_date",
    "disposed",
    "annual_book_dep",
    "prior_accum_book_dep",
    "current_book_dep",
    "accum_book_dep",
    "net_book_value",
]

PER_CLASS_COLUMNS = [
    "cca_class",
    "rate",
    "opening_ucc",
    "additions",
    "disposals",
    "half_year_adjustment",
    "cca_base",
    "cca",
    "recapture",
    "terminal_loss",
    "closing_ucc",
    "net_book_value",
    "temporary_difference",
]


def read_assets(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [validate_asset_row(row) for row in csv.DictReader(handle)]


def read_opening(path):
    opening = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cca_class, value = validate_opening_row(row)
            opening[cca_class] = value
    return opening


def _format_row(row, columns):
    out = {}
    for col in columns:
        value = row[col]
        out[col] = "Y" if value is True else "N" if value is False else str(value)
    return out


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(_format_row(row, columns))


def main(argv=None):
    parser = argparse.ArgumentParser(description="CRA CCA and book depreciation engine.")
    parser.add_argument("--assets", default="sample_assets.csv", help="asset register CSV")
    parser.add_argument("--opening", default="opening_ucc.csv", help="opening UCC by class CSV")
    parser.add_argument("--year", type=int, default=DEFAULT_TAX_YEAR, help="tax year")
    parser.add_argument(
        "--asset-out", default="per_asset_schedule.csv", help="per-asset output CSV"
    )
    parser.add_argument(
        "--class-out", default="per_class_cca.csv", help="per-class output CSV"
    )
    args = parser.parse_args(argv)

    try:
        assets = read_assets(args.assets)
        opening = read_opening(args.opening)
    except ValidationError as error:
        print("Input rejected. %s" % error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print("File not found: %s" % error.filename, file=sys.stderr)
        return 1

    per_asset, per_class = compute_schedules(assets, opening, args.year)

    write_csv(args.asset_out, PER_ASSET_COLUMNS, per_asset)
    write_csv(args.class_out, PER_CLASS_COLUMNS, per_class)

    print("Tax year %d" % args.year)
    print("Assets processed: %d" % len(per_asset))
    print("Classes rolled forward: %d" % len(per_class))
    print()
    print("Per-class CCA summary:")
    header = "  %-6s %12s %12s %12s %12s %12s" % (
        "Class", "Opening UCC", "Additions", "Disposals", "CCA", "Closing UCC"
    )
    print(header)
    for row in per_class:
        print("  %-6s %12s %12s %12s %12s %12s" % (
            row["cca_class"], row["opening_ucc"], row["additions"],
            row["disposals"], row["cca"], row["closing_ucc"],
        ))
        if row["recapture"] != Decimal("0.00"):
            print("        recapture of %s added back to income" % row["recapture"])
        if row["terminal_loss"] != Decimal("0.00"):
            print("        terminal loss of %s deducted" % row["terminal_loss"])
    print()
    print("Wrote %s and %s" % (args.asset_out, args.class_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
