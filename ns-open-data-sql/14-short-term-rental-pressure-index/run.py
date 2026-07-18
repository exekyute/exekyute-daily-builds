#!/usr/bin/env python3
"""Thin driver for the short-term-rental pressure index SQL pipeline.

No analysis lives here. Every count, share, rank, and ordering is defined in the
sql/ files. This script only sequences those files against DuckDB in order, then
checks the generated out/ file against the committed golden copy in expected/.

Usage:
    python run.py            runs the SQL end to end, then verifies out vs expected
    python run.py verify     re-runs the out vs expected diff only
    python run.py show       prints the region pressure ranking as an aligned table
"""

import csv
import os
import sys
from itertools import zip_longest

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(HERE, "sql")
OUT_FILE = os.path.join(HERE, "out", "str_pressure_index.csv")
EXPECTED_FILE = os.path.join(HERE, "expected", "str_pressure_index.csv")

# executed in this exact order against one connection
SQL_STEPS = [
    "00_schema.sql",
    "01_load.sql",
    "02_transform.sql",
    "03_analysis.sql",
    "99_export.sql",
]


def build():
    """Run each SQL step in order. All logic is in the .sql files."""
    import duckdb

    os.chdir(HERE)  # so relative paths inside the sql files resolve to this folder
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "bi", "exports"), exist_ok=True)
    con = duckdb.connect()  # in-memory; leaves no working database file behind
    try:
        for name in SQL_STEPS:
            with open(os.path.join(SQL_DIR, name), "r", encoding="utf-8") as f:
                con.execute(f.read())
    finally:
        con.close()


def _read_lines(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read().splitlines()


def verify():
    """Compare out/ to expected/ row for row. Print PASS, or the first difference."""
    if not os.path.exists(OUT_FILE):
        print("FAIL: out/str_pressure_index.csv not found. Run `python run.py` first.")
        return 1
    if not os.path.exists(EXPECTED_FILE):
        print("FAIL: expected/str_pressure_index.csv not found.")
        return 1

    out_lines = _read_lines(OUT_FILE)
    exp_lines = _read_lines(EXPECTED_FILE)

    if out_lines == exp_lines:
        print("PASS: out/str_pressure_index.csv matches expected "
              f"({max(len(out_lines) - 1, 0)} data rows).")
        return 0

    print("FAIL: out/str_pressure_index.csv differs from expected/str_pressure_index.csv")
    for i, (got, want) in enumerate(zip_longest(out_lines, exp_lines), start=1):
        if got != want:
            print(f"  first difference at line {i}:")
            print(f"    out/     : {got!r}")
            print(f"    expected/: {want!r}")
            break
    print(f"  out/ has {len(out_lines)} lines, expected/ has {len(exp_lines)} lines.")
    return 1


def show():
    """Print the exported ranking as an aligned plain-ASCII table.

    Formatting only: the columns and their order are exactly what 99_export.sql
    wrote, and the row order is the file's own.
    """
    if not os.path.exists(OUT_FILE):
        build()
    with open(OUT_FILE, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        print("out/str_pressure_index.csv is empty.")
        return 1
    widths = [
        max(len(row[i]) for row in rows)
        for i in range(len(rows[0]))
    ]
    def fmt(row):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()
    print(fmt(rows[0]))
    print("  ".join("-" * w for w in widths))
    for row in rows[1:]:
        print(fmt(row))
    return 0


def main():
    args = sys.argv[1:]
    if args and args[0] == "verify":
        sys.exit(verify())
    if args and args[0] == "show":
        sys.exit(show())
    build()
    sys.exit(verify())


if __name__ == "__main__":
    main()
