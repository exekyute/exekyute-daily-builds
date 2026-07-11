#!/usr/bin/env python3
"""Thin driver for the municipal surplus/deficit league table.

All analytical logic lives in sql/. This file holds none of it. It only:
  1. connects DuckDB (in memory, so no working files are left behind),
  2. runs sql/00_schema.sql .. sql/99_export.sql in order
     (clean slate, load snapshot, transform, analyse, export),
  3. compares out/surplus_league.csv against expected/surplus_league.csv
     row for row and prints PASS when they match, otherwise the first
     differing rows, and exits non-zero.

Usage:
  python run.py          run the SQL end to end, then verify
  python run.py verify   re-run only the golden diff
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "surplus_league.csv")
EXPECTED = os.path.join(HERE, "expected", "surplus_league.csv")


def build():
    """Execute every sql/*.sql file in filename order."""
    import duckdb

    con = duckdb.connect()  # in-memory database, nothing persisted to disk
    try:
        for path in sorted(glob.glob(os.path.join(HERE, "sql", "*.sql"))):
            with open(path, "r", encoding="utf-8") as handle:
                con.execute(handle.read())
            print("ran sql/" + os.path.basename(path))
    finally:
        con.close()


def read_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def verify():
    """Diff out/ against expected/ and print PASS or the first difference."""
    if not os.path.exists(OUT):
        print("FAIL: out/surplus_league.csv not found. Run `python run.py` first.")
        return 1
    if not os.path.exists(EXPECTED):
        print("FAIL: expected/surplus_league.csv not found.")
        return 1

    got = read_lines(OUT)
    want = read_lines(EXPECTED)

    if got == want:
        print("PASS: out/surplus_league.csv matches expected/surplus_league.csv "
              "(" + str(max(len(got) - 1, 0)) + " data rows).")
        return 0

    print("FAIL: out/surplus_league.csv differs from expected/surplus_league.csv.")
    print("  out data rows: " + str(max(len(got) - 1, 0))
          + ", expected data rows: " + str(max(len(want) - 1, 0)))
    for i in range(min(len(got), len(want))):
        if got[i] != want[i]:
            print("  first differing line (" + str(i + 1) + "):")
            print("    expected: " + want[i])
            print("    got:      " + got[i])
            return 1
    # No line differed within the shared length: one file is longer than the other.
    shared = min(len(got), len(want))
    longer, label = (got, "out") if len(got) > len(want) else (want, "expected")
    print("  " + label + " has an extra line " + str(shared + 1) + ": " + longer[shared])
    return 1


def main():
    os.chdir(HERE)  # so relative paths inside sql/ resolve against this folder
    if sys.argv[1:2] == ["verify"]:
        sys.exit(verify())
    build()
    sys.exit(verify())


if __name__ == "__main__":
    main()
