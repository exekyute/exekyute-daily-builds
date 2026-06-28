"""Command-line wrapper for the excise duty engine.

Reads the finished-unit costs from the batch tool, which carry each packaging
run's volume and ABV class, threads them through the CRA reduced-rate brackets
starting from the beer already brewed this year, and writes excise_summary.csv,
one row per ABV class. The margin tool and the month-end close read it.

Usage:
    python cli.py --in finished_unit_costs.csv --ytd-hl 1960.00 --out excise_summary.csv
    python cli.py --in finished_unit_costs.csv --ytd-hl 1960.00
"""

import argparse
import csv
import os
import sys
from decimal import Decimal

from excise import run_excise, total_duty
from validation import ValidationError, validate

OUTPUT_COLUMNS = ("abv_class", "hectolitres", "excise_duty")


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [dict(r) for r in reader]
    return header, rows


def _format(value):
    return str(value) if isinstance(value, Decimal) else value


def write_output(path, summary):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_COLUMNS)
        for row in summary:
            writer.writerow([_format(row[c]) for c in OUTPUT_COLUMNS])


def print_summary(summary, cumulative, ytd):
    print("Federal beer excise duty (CRA rates, April 1, 2026)")
    print("  beer brewed this year before this run : %s hL" % Decimal(str(ytd)))
    print("  beer brewed this year after this run  : %s hL"
          % cumulative.quantize(Decimal("0.01")))
    print("")
    print("  %-18s %14s %14s" % ("ABV class", "hectolitres", "duty"))
    print("  " + "-" * 48)
    for row in summary:
        print("  %-18s %14s %14s" % (row["abv_class"], row["hectolitres"], "$" + str(row["excise_duty"])))
    print("  " + "-" * 48)
    print("  %-18s %14s %14s" % ("total", "", "$" + str(total_duty(summary))))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Federal beer excise duty engine.")
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--ytd-hl", dest="ytd_hl", default="0",
                        help="beer of every class already brewed this calendar year, in hL")
    parser.add_argument("--out", dest="out_path")
    args = parser.parse_args(argv)

    if not os.path.exists(args.in_path):
        print("input file not found: %s" % args.in_path, file=sys.stderr)
        return 2

    header, rows = read_rows(args.in_path)
    try:
        validate(rows, header, args.ytd_hl)
    except ValidationError as error:
        print("Input rejected. Nothing was written.\n", file=sys.stderr)
        for problem in error.problems:
            print("  - %s" % problem, file=sys.stderr)
        return 1

    events = [{"abv_class": r["abv_class"].strip(),
               "litres": Decimal(r["packaged_litres"].strip())} for r in rows]
    summary, cumulative = run_excise(events, Decimal(args.ytd_hl))
    print_summary(summary, cumulative, args.ytd_hl)

    if args.out_path:
        write_output(args.out_path, summary)
        print("\nWrote %d rows to %s" % (len(summary), args.out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
