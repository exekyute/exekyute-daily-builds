"""Command line front end for the Regional Waste and Fuel Log Aggregator.

This file is a thin wrapper. It reads the folder of site files, asks core.py to
do the real work, writes the unified ledger, and prints a plain summary so you
can see exactly what was combined and what was rejected and why.

Usage:
    python aggregate_cli.py
    python aggregate_cli.py --data data --out output/unified_ledger.csv
"""

import argparse
import os

import core

HERE = os.path.dirname(__file__)
DEFAULT_DATA = os.path.join(HERE, "data")
DEFAULT_OUT = os.path.join(HERE, "output", "unified_ledger.csv")


def main():
    parser = argparse.ArgumentParser(
        description="Combine monthly site spreadsheets into one unified ledger."
    )
    parser.add_argument(
        "--data", default=DEFAULT_DATA,
        help="folder of monthly site CSV files (default: data)",
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT,
        help="where to write the unified ledger (default: output/unified_ledger.csv)",
    )
    args = parser.parse_args()

    paths = core.find_input_files(args.data)
    if not paths:
        print(f"No .csv files found in {args.data}")
        print("Run 'python generate_samples.py' first to create the sample data.")
        return

    result = core.combine_files(paths)
    core.write_ledger(result["records"], args.out)

    # ---- Summary dashboard -------------------------------------------------
    print()
    print("REGIONAL WASTE AND FUEL LOG AGGREGATOR")
    print("=" * 50)
    print(f"Files read:      {len(result['files_used'])}")
    print(f"Rows combined:   {len(result['records'])}")
    print(f"Rows skipped:    {len(result['skipped'])}")
    print(f"Distinct sites:  {len(result['sites'])}  ({', '.join(result['sites'])})")
    print(f"Ledger written:  {args.out}")

    if result["files_skipped"]:
        print()
        print("Files skipped (unusable):")
        for name, reason in result["files_skipped"]:
            print(f"  - {name}: {reason}")

    if result["skipped"]:
        print()
        print("Rows skipped (bad data):")
        for source, reason in result["skipped"]:
            print(f"  - {source}: {reason}")

    print()
    print("Unified ledger:")
    print(f"  {'site':<14}{'month':<10}{'waste_tons':>12}{'fuel_gallons':>14}")
    for record in result["records"]:
        print(
            f"  {record['site']:<14}{record['month']:<10}"
            f"{core.format_quantity(record['waste_tons']):>12}"
            f"{core.format_quantity(record['fuel_gallons']):>14}"
        )
    print()


if __name__ == "__main__":
    main()
